# india-flood-risk

Flood risk, crop-insurance claims and the protection gap in India: one district-level model built on public data.

The pipeline runs in four steps:

1. Daily rainfall goes in.
2. **Part A** forecasts which districts flood each monsoon, and how much damage a state reports in a flood year.
3. **Part B** tests whether that forecast explains PMFBY crop-insurance claims.
4. **Part C** measures the protection gap: people at flood risk for each ₹1 crore of property and crop premium.

Every model is fitted on monsoons up to 2012 and scored once on later years against a simple baseline. Every result carries a 95% bootstrap interval.

- Live demo: https://vivekmitra.com/india-flood.html
- Paper: https://vivekmitra.com/papers/india-flood.pdf

## Results (held-out years)

<!-- results -->
Gains are computed from unrounded errors.

| Part | Held-out measure | Model | Baseline | Gain (95% interval) | Verdict |
| --- | --- | ---: | ---: | ---: | --- |
| A districts | AUC 2013-2020 | 0.828 | 0.806 | +0.022 (+0.015 to +0.031) | better |
| A districts | AUC 2021-2023 | 0.797 | 0.767 | +0.030 (+0.018 to +0.042) | better |
| A states | people affected: mean log error 2013-2020 | 1.781 | 1.913 | +0.13 (+0.01 to +0.23) | better |
| A states | houses damaged: mean log error 2013-2020 | 1.753 | 1.902 | +0.15 (+0.03 to +0.28) | better |
| A states | crop area hit: mean log error 2013-2020 | 1.645 | 1.722 | +0.08 (-0.02 to +0.17) | no clear difference |
| A states | lives lost: mean log error 2013-2020 | 0.854 | 0.943 | +0.09 (+0.05 to +0.13) | better |
| B claims | log claims error, flood share from A | 0.7373 | 0.7288 | -0.009 (-0.024 to +0.009) | no clear difference |
| B claims | log claims error, monsoon total vs normal | 0.7105 | 0.7288 | +0.018 (-0.022 to +0.059) | no clear difference |

Widest protection gaps, as people at flood risk per ₹1 crore of fire + PMFBY premium: Bihar (238,472), Manipur (83,250), Kerala (56,362). India: 6,696.
<!-- /results -->

## Run it

You need Python 3.11 or newer. Node 22 and Microsoft Word are needed only to rebuild the paper.

```
python -m venv .venv
.venv\Scripts\activate            (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
python get_data.py                (downloads about 1.2 GB into data/; no keys or logins)
python run_all.py                 (rebuilds every number, the site data, the figures and the paper)
```

If the IMD server is slow, run `get_data.py` again. It skips files it already has.

| File | What it does |
| --- | --- |
| `get_data.py` | Downloads the public inputs into `data/` |
| `step1_tables.py` | Cleans the Census, Flood Inventory, CWC, PMFBY and premium tables. It checks the parsed rows against the totals printed in the sources. |
| `step2_rain.py` | IMD 0.25° daily rainfall → wettest 3 days and monsoon total for each district and year |
| `step3_damage.py` | Part A: district flood chance (logistic regression) and state damage (linear regression on logs) |
| `step4_claims.py` | Part B: PMFBY claims vs the flood forecast and the monsoon total |
| `step5_gap.py` | Part C: people at flood risk per ₹1 crore of fire and PMFBY premium |
| `step6_site.py` | Writes the demo's data files and this README's results table |
| `step7_figures.py` | The paper's figures |
| `test_check.py` | Checks the fitted models by hand: the logistic score is zero, OLS satisfies the normal equations, AUC equals the pair count, and the page formula reproduces Python |
| `paper/` | Builds the paper (.docx and PDF) from `results/` and checks every number in it |

## Data

| Source | Used for | Licence or terms |
| --- | --- | --- |
| India Meteorological Department, 0.25° gridded daily rainfall (Pai et al., 2014) | Rainfall, 1981-2023 | Free public download from imdpune.gov.in |
| India Flood Inventory v3 (Saharia et al., 2021), Zenodo record 16994648 | Flooded districts by monsoon | CC BY-NC 4.0 (non-commercial) |
| Central Water Commission, state-wise flood damage 1953-2020 | State damage | Government of India publication |
| Press Information Bureau release 1941399 | PMFBY premium and claims by state, 2016-17 to 2022-23 | Government of India publication |
| General Insurance Council, Non-Life Industry Yearbook 2024-25 | State fire premium | Public publication |
| Census of India 2011, Primary Census Abstract (via github.com/pigshell/india-census-2011) | District population | Government of India data; scraper MIT |
| DataMeet India maps: Census 2011 districts and India outline | Map and district geometry | CC BY 4.0. Shows India's official boundaries. |

`data/` is not part of the repository: `get_data.py` downloads it.

## Licence

Copyright (C) 2026 Vivek Mitra. Licensed under the GNU Affero General Public License v3.0. See `LICENSE`.
