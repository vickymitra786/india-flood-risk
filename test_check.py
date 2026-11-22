"""Small checks that the maths is what the paper says. Run by run_all.py (or alone).

1. Logistic regression: at the fitted coefficients the score X'(y - p) is zero (the maximum-likelihood
   condition), checked by hand with numpy on the real training rows.
2. Linear regression: the coefficients solve the normal equations X'X b = X'y, solved by hand.
3. AUC by ranks equals the share of (flooded, dry) pairs ranked correctly, counted pair by pair.
4. The JSON the page reads gives the same district probabilities when the formula is applied by hand.
Author: Vivek Mitra
"""
import json

import numpy as np
import pandas as pd
import statsmodels.api as sm

from common import RES, SITE, TRAIN_END
from step3_damage import district_table, FEATS, auc

d, x, _ = district_table()
tr = x[x.year <= TRAIN_END]
X = sm.add_constant(tr[FEATS]).to_numpy()
fit = sm.Logit(tr.flood, sm.add_constant(tr[FEATS])).fit(disp=0)
p = 1 / (1 + np.exp(-X @ fit.params.to_numpy()))
score = X.T @ (tr.flood.to_numpy() - p)
assert np.abs(score).max() < 1e-4 * len(tr), score
a = json.load(open(RES / "part_a.json"))
assert np.allclose(fit.params.to_numpy(), list(a["a1_district"]["coef"].values())), "part_a.json is stale"

rng = np.random.default_rng(0)
Z = np.c_[np.ones(50), rng.normal(size=(50, 2))]
yz = Z @ [1.0, 2.0, -0.5] + rng.normal(size=50)
assert np.allclose(np.linalg.solve(Z.T @ Z, Z.T @ yz), sm.OLS(yz, Z).fit().params)

y = rng.integers(0, 2, 300)
s = rng.normal(size=300) + y
pairs = np.mean([(si > sj) + 0.5 * (si == sj) for si, yi in zip(s, y) if yi for sj, yj in zip(s, y) if not yj])
assert abs(pairs - auc(y, s)) < 1e-12

site = json.load(open(SITE / "data/india-flood.json", encoding="utf-8"))
c = site["a1"]["coef"]
yr = str(site["years"][0])
for i in range(0, len(site["districts"]), 37):
    dd, v = site["districts"][i], site["by_year"][yr]
    if dd["h"] is None:
        continue
    r3 = np.clip(np.log(max(v["rx3"][i], 1) / max(dd["rx3n"], 1)), -1.5, 1.5)
    se = np.clip(np.log(max(v["tot"][i], 1) / max(dd["totn"], 1)), -1.5, 1.5)
    ph = 1 / (1 + np.exp(-(c["const"] + c["history"] * dd["h"] + c["r3"] * r3 + c["season"] * se)))
    assert abs(ph - v["p"][i]) < 1e-4, (i, ph, v["p"][i])
print("  checks passed: logistic score = 0, OLS normal equations, AUC by pairs, page formula = Python")
