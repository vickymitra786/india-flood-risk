"""Part A: rainfall -> flood damage. Fit on monsoons up to 2012, test once on 2013 onwards.

A1 District: was the district flooded this monsoon (India Flood Inventory)?
   Logistic regression  logit p = b0 + b1*history + b2*log(rx3/normal) + b3*log(total/normal)
   Baseline: the district's own flood rate in the training years.
A2 State: in a year when the state reports flood damage (CWC, 2001-2020), how large is it?
   Targets: people affected, houses damaged, crop area hit, lives lost.
   Linear regression  log(damage) = state average + b*share, where share is the population-weighted
   average of the A1 district probabilities (the expected share of people in flooded districts).
   Baseline: the state's average log damage in the training years.
Author: Vivek Mitra
"""
import json

import numpy as np
import pandas as pd
import statsmodels.api as sm

from common import CLEAN, RES, TRAIN_END

RNG = np.random.default_rng(2026)
B = 2000                                   # bootstrap resamples
TARGETS = {"people": ("pop_m", 1e6), "houses": ("houses", 1), "crop_ha": ("crop_mha", 1e6), "lives": ("lives", 1)}


def auc(y, p):
    """Probability that a random flooded district-year gets a higher score than a random dry one."""
    r = pd.Series(p).rank().to_numpy()
    n1 = y.sum()
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * (len(y) - n1))


def logloss(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))


def boot(groups, stat):
    """Paired bootstrap: resample whole groups (districts or states) with replacement, recompute stat."""
    ids = np.unique(groups)
    pos = {g: np.flatnonzero(groups == g) for g in ids}
    out = [stat(np.concatenate([pos[g] for g in RNG.choice(ids, len(ids))])) for _ in range(B)]
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def district_table():
    d = pd.read_csv(CLEAN / "districts.csv")
    d = d[d["pop"] > 0]                                    # drops the unpopulated 'Data Not Available' polygon
    x = pd.read_csv(CLEAN / "rain.csv").merge(pd.read_csv(CLEAN / "ifi_flood.csv"), on=["id", "year"])
    x = x[x.id.isin(d.id)]
    norm = x[x.year.between(1981, 2010)].groupby("id")[["rx3", "tot"]].median().add_suffix("_norm")
    hist = x[x.year <= TRAIN_END].groupby("id").flood.agg(["sum", "count"])
    hist["rate"] = (hist["sum"] + 0.5) / (hist["count"] + 1)           # smoothed so no district is exactly 0
    x = x.join(norm, on="id").join(hist.rate, on="id").join(hist[["sum", "count"]], on="id")
    # A training row must not see its own outcome, so its history leaves that year out.
    own = x.year <= TRAIN_END
    x["h_rate"] = np.where(own, (x["sum"] - x.flood + 0.5) / x["count"], x.rate)
    x["history"] = np.log(x.h_rate / (1 - x.h_rate))
    # log ratios to the district's normal, capped at a factor of e^1.5 = 4.5 (chosen by cross-validation
    # within the training years) so that desert districts with tiny normals do not give extreme values
    x["r3_raw"] = np.log(np.maximum(x.rx3, 1) / np.maximum(x.rx3_norm, 1))
    x["season_raw"] = np.log(np.maximum(x.tot, 1) / np.maximum(x.tot_norm, 1))
    x["r3"], x["season"] = x.r3_raw.clip(-1.5, 1.5), x.season_raw.clip(-1.5, 1.5)
    return d, x, norm.join(hist.rate)


FEATS = ["history", "r3", "season"]


def part_a1(x):
    tr, te = x[x.year <= TRAIN_END], x[x.year > TRAIN_END]
    fit = sm.Logit(tr.flood, sm.add_constant(tr[FEATS])).fit(disp=0)
    x["p"] = fit.predict(sm.add_constant(x[FEATS]))
    res = {"coef": dict(zip(["const"] + FEATS, map(float, fit.params))),
           "coef_se": dict(zip(["const"] + FEATS, map(float, fit.bse))),
           "n_train": int(len(tr)), "train_years": [int(tr.year.min()), TRAIN_END]}
    for name, part in {"2013-2020": te[te.year <= 2020], "2021-2023": te[te.year > 2020], "2013-2023": te}.items():
        y, pm, pb = part.flood.to_numpy(), x.loc[part.index, "p"].to_numpy(), part.rate.to_numpy()
        g = part.id.to_numpy()
        res[name] = {
            "n": int(len(y)), "flooded_share": float(y.mean()),
            "auc_model": auc(y, pm), "auc_base": auc(y, pb),
            "auc_gain": auc(y, pm) - auc(y, pb),
            "auc_gain_ci": boot(g, lambda i: auc(y[i], pm[i]) - auc(y[i], pb[i])),
            "logloss_model": logloss(y, pm), "logloss_base": logloss(y, pb),
            "logloss_cut": logloss(y, pb) - logloss(y, pm),
            "logloss_cut_ci": boot(g, lambda i: logloss(y[i], pb[i]) - logloss(y[i], pm[i])),
            "mean_p_model": float(pm.mean()), "mean_p_base": float(pb.mean()),
        }
    return res


def part_a2(x, d):
    x = x.merge(d[["id", "state", "pop"]], on="id")
    x["pp"], x["ps"] = x.p * x["pop"], x.season * x["pop"]
    e = x.groupby(["state", "year"])[["pp", "ps", "pop"]].sum()
    # share: expected share of people in flooded districts; season: population-weighted monsoon anomaly
    e = pd.DataFrame({"share": e.pp / e["pop"], "season": e.ps / e["pop"]}).reset_index()
    cwc = pd.read_csv(CLEAN / "cwc_damage.csv")
    s = cwc[cwc.year.between(2001, 2020)].merge(e, on=["state", "year"])
    out, preds = {}, []
    for t, (col, scale) in TARGETS.items():
        z = s[s[col] > 0].copy()                              # years with reported damage
        z["ly"] = np.log(z[col] * scale)
        tr = z[z.year <= TRAIN_END]
        keep = tr.groupby("state").size()
        keep = keep[keep >= 5].index                          # a state needs 5 reported training years
        z, tr = z[z.state.isin(keep)], tr[tr.state.isin(keep)]
        te = z[z.year > TRAIN_END]
        X = lambda f: pd.get_dummies(f.state).reindex(columns=keep, fill_value=0).astype(float).assign(share=f.share)
        fit = sm.OLS(tr.ly, X(tr)).fit()
        sigma = float(np.sqrt(fit.scale))
        base = tr.groupby("state").ly.mean()
        sig_b = float(np.sqrt(((tr.ly - tr.state.map(base)) ** 2).sum() / (len(tr) - len(keep))))
        pm, pb = fit.predict(X(te)).to_numpy(), te.state.map(base).to_numpy()
        y, g = te.ly.to_numpy(), te.state.to_numpy()
        mae = lambda p, i=slice(None): float(np.mean(np.abs(y[i] - p[i])))
        out[t] = {"n_train": int(len(tr)), "n_test": int(len(te)), "states": len(keep),
                  "slope": float(fit.params["share"]), "slope_se": float(fit.bse["share"]),
                  "sigma": sigma, "sigma_base": sig_b,
                  "mae_model": mae(pm), "mae_base": mae(pb), "mae_cut": mae(pb) - mae(pm),
                  "mae_cut_ci": boot(g, lambda i: mae(pb, i) - mae(pm, i)),
                  "cover80_model": float(np.mean(np.abs(y - pm) <= 1.2816 * sigma)),
                  "cover80_base": float(np.mean(np.abs(y - pb) <= 1.2816 * sig_b)),
                  "state_mean": {k: float(v) for k, v in fit.params.drop("share").items()}}
        te = te.assign(target=t, pred=pm, base=pb, lo=pm - 1.2816 * sigma, hi=pm + 1.2816 * sigma)
        preds.append(te[["state", "year", "target", "ly", "pred", "base", "lo", "hi", "share"]])
    return out, pd.concat(preds), e


def training_cv(x, d):
    """The two design choices, made by leaving one training year out at a time (no test year is used).
    1. Cap the rainfall ratios or not (Part A districts, log loss).
    2. Which state feature sizes damage best (Part A states, mean absolute log error). Uses the A1 chances."""
    tr = x[x.year <= TRAIN_END]

    def a1_loss(feats):
        tot = 0.0
        for y in sorted(tr.year.unique()):
            a, b = tr[tr.year != y], tr[tr.year == y]
            p = sm.Logit(a.flood, sm.add_constant(a[feats])).fit(disp=0).predict(sm.add_constant(b[feats], has_constant="add"))
            tot += logloss(b.flood.to_numpy(), p.to_numpy()) * len(b)
        return tot / len(tr)

    clip = {"unclipped": a1_loss(["history", "r3_raw", "season_raw"]), "clipped": a1_loss(FEATS)}
    z = x[x.year.between(2001, TRAIN_END)].merge(d[["id", "state", "pop"]], on="id")
    g = z.assign(pp=z.p * z["pop"], rp=z.r3 * z["pop"], sp=z.season * z["pop"]).groupby(["state", "year"])
    f = pd.DataFrame({"share": g.pp.sum() / g["pop"].sum(), "log_expected": np.log(g.p.sum()),
                      "r3_mean": g.rp.sum() / g["pop"].sum(), "s_mean": g.sp.sum() / g["pop"].sum(),
                      "r3_max": g.r3.max()}).reset_index()
    s = pd.read_csv(CLEAN / "cwc_damage.csv").merge(f, on=["state", "year"])
    cands = {"state average": [], "share": ["share"], "log expected floods": ["log_expected"],
             "mean r3": ["r3_mean"], "mean r3 and s": ["r3_mean", "s_mean"], "max r3": ["r3_max"]}
    out = {}
    for t, (col, scale) in TARGETS.items():
        q = s[s[col] > 0].copy()
        q["ly"] = np.log(q[col] * scale)
        n = q.groupby("state").size()
        q = q[q.state.isin(n[n >= 5].index)]
        st = sorted(q.state.unique())
        out[t] = {}
        for name, F in cands.items():
            err = []
            for y in sorted(q.year.unique()):
                a, b = q[q.year != y], q[q.year == y]
                X = lambda h: pd.get_dummies(h.state).reindex(columns=st, fill_value=0).astype(float).join(h[F])
                err += list(np.abs(b.ly - sm.OLS(a.ly, X(a)).fit().predict(X(b))))
            out[t][name] = float(np.mean(err))
    return {"clip": clip, "a2_features": out}


EVENTS = [("Uttarakhand", 2013), ("Kerala", 2018), ("Bihar", 2019), ("Assam", 2019), ("Himachal Pradesh", 2023)]


def events(x, d, preds):
    """Named floods in the test years: districts flooded vs expected, and state damage vs forecast."""
    x = x.merge(d[["id", "state"]], on="id")
    out = []
    for st, y in EVENTS:
        z = x[(x.state == st) & (x.year == y)]
        e = {"state": st, "year": y, "districts": int(len(z)), "flooded": int(z.flood.sum()),
             "expected": float(z.p.sum()), "expected_history": float(z.rate.sum()),
             "p_flooded": float(z.p[z.flood == 1].mean()) if z.flood.any() else None,
             "p_dry": float(z.p[z.flood == 0].mean()) if (z.flood == 0).any() else None}
        for _, r in preds[(preds.state == st) & (preds.year == y)].iterrows():
            e[r.target] = {"actual": float(np.exp(r.ly)), "model": float(np.exp(r.pred)), "base": float(np.exp(r.base)),
                           "lo": float(np.exp(r.lo)), "hi": float(np.exp(r.hi))}
        out.append(e)
    return out


if __name__ == "__main__":
    RES.mkdir(exist_ok=True)
    d, x, norms = district_table()
    a1 = part_a1(x)
    a2, a2_pred, expected = part_a2(x, d)
    x[["id", "year", "rx3", "tot", "flood", "p"]].to_csv(CLEAN / "district_years.csv", index=False)
    norms.to_csv(CLEAN / "district_norms.csv")
    expected.to_csv(CLEAN / "state_expected.csv", index=False)
    a2_pred.to_csv(RES / "a2_test_predictions.csv", index=False)
    json.dump({"a1_district": a1, "a2_state": a2, "events": events(x, d, a2_pred), "training_cv": training_cv(x, d)},
              open(RES / "part_a.json", "w"), indent=1)
    for k in ["2013-2020", "2021-2023"]:
        r = a1[k]
        print(f"  A1 {k}: AUC {r['auc_model']:.3f} vs history {r['auc_base']:.3f} "
              f"(gain {r['auc_gain']:+.3f}, 95% CI {r['auc_gain_ci'][0]:+.3f} to {r['auc_gain_ci'][1]:+.3f})")
    for t, r in a2.items():
        print(f"  A2 {t}: MAE(log) {r['mae_model']:.2f} vs {r['mae_base']:.2f} cut {r['mae_cut']:+.2f} "
              f"CI {r['mae_cut_ci'][0]:+.2f}..{r['mae_cut_ci'][1]:+.2f}; 80% cover {r['cover80_model']:.0%}")
