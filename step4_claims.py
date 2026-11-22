"""Part B: does Part A's flood forecast help explain PMFBY crop-insurance claims?

Data: PMFBY gross premium and paid claims by state and crop year, 2016-17 to 2021-22 (PIB).
2022-23 is left out because its claims were still being paid (5,761 of about 20,000 crore).
Model:    log(claims / premium) = state average + g * feature
Baseline: log(claims / premium) = state average          (each state's usual loss ratio)
Two features are tested, one at a time:
  share   Part A's expected share of the state's people in flooded districts for that monsoon
  season  the monsoon total vs normal (log ratio, population-weighted), which also captures drought
Only state level is possible: no public district-by-season claims table was found.
Test: leave one crop year out, six times; paired bootstrap over states for the error difference.
Author: Vivek Mitra
"""
import json

import numpy as np
import pandas as pd
import statsmodels.api as sm

from common import CLEAN, RES
from step3_damage import boot


def table():
    c = pd.read_csv(CLEAN / "pmfby.csv")
    c = c[(c.crop_year <= 2021) & (c.premium_cr > 0)]
    zero = int((c.claims_cr <= 0).sum())
    c = c[c.claims_cr > 0]
    e = pd.read_csv(CLEAN / "state_expected.csv").rename(columns={"year": "crop_year"})
    c = c.merge(e, on=["state", "crop_year"])
    n = c.groupby("state").size()
    c = c[c.state.isin(n[n >= 3].index)].copy()          # a state needs 3 crop years
    c["lr"] = np.log(c.claims_cr / c.premium_cr)
    return c, zero


def X(f, states, feat):
    return pd.get_dummies(f.state).reindex(columns=states, fill_value=0).astype(float).assign(**{feat: f[feat]})


def test(c, feat):
    states = sorted(c.state.unique())
    pm, pb = pd.Series(index=c.index, dtype=float), pd.Series(index=c.index, dtype=float)
    for y in sorted(c.crop_year.unique()):
        tr, te = c[c.crop_year != y], c[c.crop_year == y]
        pm[te.index] = sm.OLS(tr.lr, X(tr, states, feat)).fit().predict(X(te, states, feat))
        pb[te.index] = te.state.map(tr.groupby("state").lr.mean())
    y, m, b, g = c.lr.to_numpy(), pm.to_numpy(), pb.to_numpy(), c.state.to_numpy()
    mae = lambda p, i=slice(None): float(np.mean(np.abs(y[i] - p[i])))
    full = sm.OLS(c.lr, X(c, states, feat)).fit()
    return {"mae_model": mae(m), "mae_base": mae(b), "mae_cut": mae(b) - mae(m),
            "mae_cut_ci": boot(g, lambda i: mae(b, i) - mae(m, i)),
            "slope": float(full.params[feat]), "slope_se": float(full.bse[feat]),
            "slope_p": float(full.pvalues[feat])}


if __name__ == "__main__":
    c, zero = table()
    out = {"n": len(c), "states": int(c.state.nunique()), "years": [int(c.crop_year.min()), int(c.crop_year.max())],
           "zero_claim_rows_dropped": zero,
           "share": test(c, "share"), "season": test(c, "season"),
           "state_mean": {k: float(v) for k, v in c.groupby("state").lr.mean().items()},
           "premium_recent_cr": {k: float(v) for k, v in
                                 c[c.crop_year >= 2019].groupby("state").premium_cr.mean().items()}}
    json.dump(out, open(RES / "part_b.json", "w"), indent=1)
    for f in ["share", "season"]:
        r = out[f]
        print(f"  B {f}: {out['n']} state-years, {out['states']} states. MAE(log claims) {r['mae_model']:.3f} vs "
              f"{r['mae_base']:.3f} (cut {r['mae_cut']:+.3f}, 95% CI {r['mae_cut_ci'][0]:+.3f} to "
              f"{r['mae_cut_ci'][1]:+.3f}); slope {r['slope']:.2f} +/- {r['slope_se']:.2f}")
