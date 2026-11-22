"""Part C: protection gap. Where is flood risk high but flood-relevant insurance low?

risk     people in districts expected to flood in a monsoon: sum over districts of p * population,
         where p is Part A's district flood probability averaged over the 1981-2023 monsoons
premium  fire (property) premium 2024-25 (GI Council yearbook) + PMFBY crop premium, average of
         crop years 2019-20 to 2021-22 (PIB), in Rs crore
gap      people at flood risk per Rs 1 crore of that premium (higher = less cover)
Districts get their state's premium in proportion to population (no district premium is published).
Rupee losses are not used: the CWC rupee series is too incomplete (for example Maharashtra reports
Rs 0 for 2011-2020).
Author: Vivek Mitra
"""
import json

import pandas as pd

from common import CLEAN, RES

if __name__ == "__main__":
    d = pd.read_csv(CLEAN / "districts.csv")
    p = pd.read_csv(CLEAN / "district_years.csv").groupby("id").p.mean().rename("p_mean")
    d = d.join(p, on="id").dropna(subset=["p_mean"])
    d["at_risk"] = d.p_mean * d["pop"]
    crop = pd.read_csv(CLEAN / "pmfby.csv")
    crop = crop[crop.crop_year.between(2019, 2021)].groupby("state").premium_cr.sum() / 3
    prem = pd.read_csv(CLEAN / "premium.csv").set_index("state")
    s = d.groupby("state")[["pop", "at_risk"]].sum()
    s["fire_cr"] = prem.fire_cr
    s["crop_cr"] = crop.reindex(s.index).fillna(0)
    s["premium_cr"] = s.fire_cr + s.crop_cr
    s = s[s.premium_cr > 0]
    s["gap"] = s.at_risk / s.premium_cr
    d = d[d.state.isin(s.index)]
    d["premium_cr"] = s.premium_cr.reindex(d.state).to_numpy() * d["pop"] / s["pop"].reindex(d.state).to_numpy()
    d["gap"] = d.at_risk / d.premium_cr
    top_s = s.sort_values("gap", ascending=False)
    top_d = d.sort_values("gap", ascending=False).head(20)
    out = {"states": top_s.reset_index().round(4).to_dict("records"),
           "top20_districts": top_d[["id", "district", "state", "pop", "p_mean", "at_risk", "premium_cr", "gap"]]
           .round(4).to_dict("records"),
           "national": {"at_risk": float(s.at_risk.sum()), "premium_cr": float(s.premium_cr.sum()),
                        "gap": float(s.at_risk.sum() / s.premium_cr.sum())}}
    json.dump(out, open(RES / "part_c.json", "w"), indent=1)
    print(top_s[["at_risk", "fire_cr", "crop_cr", "gap"]].head(10).round(1).to_string())
