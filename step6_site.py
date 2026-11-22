"""Step 6: write the data files the demo page reads, plus the card for the home page.

  site/data/india-flood.json      model coefficients, district inputs for 2013-2023, test results
  site/data/india-flood-map.json  Census 2011 district shapes and the official India outline (DataMeet,
                                  CC BY 4.0), simplified; coordinates are degrees x 100, rounded
  site/data/india-flood.card.json the home-page card
Author: Vivek Mitra
"""
import json

import numpy as np
import pandas as pd
import shapefile
import shapely
from shapely.geometry import shape

from common import CLEAN, RES, SITE, DATA, HERE, TRAIN_END


def rings(geom):
    """Exterior rings of a (multi)polygon as flat integer lists [x0, y0, x1, y1, ...] in degrees x 100."""
    out = []
    for p in getattr(geom, "geoms", [geom]):
        if p.geom_type == "Polygon" and len(p.exterior.coords) >= 4:
            out.append([int(round(v * 100)) for xy in p.exterior.coords for v in xy])
    return out


def map_file():
    r = shapefile.Reader(str(DATA / "maps/2011_Dist.shp"))
    polys = [shape(s.__geo_interface__).buffer(0) for s in r.shapes()]
    simple = shapely.coverage_simplify(polys, 0.02)        # shared borders stay shared
    india = json.load(open(DATA / "maps/india-composite.geojson"))
    outline = shapely.union_all([shape(f["geometry"]) for f in india["features"]]).simplify(0.02)
    return {"source": "DataMeet India maps (CC BY 4.0): Census 2011 districts and the India composite outline",
            "districts": [rings(g) for g in simple], "outline": rings(outline)}


def readme_table(a, b, c):
    """The README's results table, rewritten from the result files on every run."""
    v = lambda ci: "better" if ci[0] > 0 else "worse" if ci[1] < 0 else "no clear difference"
    g = lambda x, ci, f: f"{x:+{f}} ({ci[0]:+{f}} to {ci[1]:+{f}})"
    rows = ["Gains are computed from unrounded errors.\n", "| Part | Held-out measure | Model | Baseline | Gain (95% interval) | Verdict |", "| --- | --- | ---: | ---: | ---: | --- |"]
    for k in ["2013-2020", "2021-2023"]:
        r = a["a1_district"][k]
        rows.append(f"| A districts | AUC {k} | {r['auc_model']:.3f} | {r['auc_base']:.3f} | {g(r['auc_gain'], r['auc_gain_ci'], '.3f')} | {v(r['auc_gain_ci'])} |")
    names = {"people": "people affected", "houses": "houses damaged", "crop_ha": "crop area hit", "lives": "lives lost"}
    for t, r in a["a2_state"].items():
        rows.append(f"| A states | {names[t]}: mean log error 2013-2020 | {r['mae_model']:.3f} | {r['mae_base']:.3f} | {g(r['mae_cut'], r['mae_cut_ci'], '.2f')} | {v(r['mae_cut_ci'])} |")
    for f, lab in [("share", "flood share from A"), ("season", "monsoon total vs normal")]:
        r = b[f]
        rows.append(f"| B claims | log claims error, {lab} | {r['mae_model']:.4f} | {r['mae_base']:.4f} | {g(r['mae_cut'], r['mae_cut_ci'], '.3f')} | {v(r['mae_cut_ci'])} |")
    top = ", ".join(f"{r['state']} ({r['gap']:,.0f})" for r in c["states"][:3])
    rows.append(f"\nWidest protection gaps, as people at flood risk per ₹1 crore of fire + PMFBY premium: {top}. "
                f"India: {c['national']['gap']:,.0f}.")
    path = HERE / "README.md"
    text = path.read_text(encoding="utf-8")
    head, rest = text.split("<!-- results -->")
    tail = rest.split("<!-- /results -->")[1]
    path.write_text(head + "<!-- results -->\n" + "\n".join(rows) + "\n<!-- /results -->" + tail, encoding="utf-8")


if __name__ == "__main__":
    a = json.load(open(RES / "part_a.json"))
    b = json.load(open(RES / "part_b.json"))
    c = json.load(open(RES / "part_c.json"))
    d = pd.read_csv(CLEAN / "districts.csv")
    norms = pd.read_csv(CLEAN / "district_norms.csv").set_index("id")
    dy = pd.read_csv(CLEAN / "district_years.csv")
    states = sorted(d.state.unique())
    prem = {r["state"]: r["premium_cr"] for r in c["states"]}
    years = sorted(int(y) for y in dy.year.unique() if y > TRAIN_END)
    dist = []
    for _, r in d.iterrows():
        n = norms.loc[r.id] if r.id in norms.index else None
        dist.append({"n": r.district, "s": states.index(r.state), "pop": int(r["pop"]),
                     "h": None if n is None else round(float(np.log(n.rate / (1 - n.rate))), 4),
                     "rx3n": None if n is None else float(n.rx3_norm), "totn": None if n is None else float(n.tot_norm)})
    by_year = {}
    for y in years:
        t = dy[dy.year == y].set_index("id").reindex(d.id)
        by_year[y] = {"rx3": [None if v != v else float(v) for v in t.rx3],
                      "tot": [None if v != v else float(v) for v in t.tot],
                      "flood": [None if v != v else int(v) for v in t.flood],
                      "p": [None if v != v else round(float(v), 4) for v in t.p]}   # Python's answer, for the JS check
    actual = pd.read_csv(RES / "a2_test_predictions.csv")
    act = {}
    for _, r in actual.iterrows():
        act.setdefault(r.state, {}).setdefault(int(r.year), {})[r.target] = round(float(np.exp(r.ly)))
    site = {"states": states, "districts": dist, "years": years, "by_year": by_year, "train_end": TRAIN_END,
            "a1": a["a1_district"], "a2": a["a2_state"], "a2_actual": act,
            "b": b, "c": {"states": c["states"], "top20": c["top20_districts"], "national": c["national"],
                          "premium_cr": prem}}
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    json.dump(site, open(SITE / "data/india-flood.json", "w", encoding="utf-8"), separators=(",", ":"))
    json.dump(map_file(), open(SITE / "data/india-flood-map.json", "w", encoding="utf-8"), separators=(",", ":"))

    t = a["a1_district"]["2013-2020"]
    top = c["states"][0]
    card = {
        "slug": "india-flood", "stage": "Catastrophe · India",
        "title": "India flood risk: districts, crop claims and the protection gap",
        "problem": "Insurers in India need to know which districts a heavy monsoon will flood, what it will "
                   "damage, and where flood cover is thinnest.",
        "headline": f"AUC {t['auc_model']:.2f} vs {t['auc_base']:.2f}",
        "headline_note": (f"ranking which of 640 districts flood in unseen monsoons 2013-2020, from IMD rainfall, "
                          f"against each district's own flood history (gain {t['auc_gain']:+.3f}, 95% interval "
                          f"{t['auc_gain_ci'][0]:+.3f} to {t['auc_gain_ci'][1]:+.3f}). {top['state']} has the "
                          f"widest protection gap."),
        "href": "india-flood.html", "paper": "papers/india-flood.pdf",
    }
    names = {"people": "people affected", "houses": "houses damaged", "crop_ha": "crop area hit", "lives": "lives lost"}
    won = [names[k] for k, v in a["a2_state"].items() if v["mae_cut_ci"][0] > 0]
    claims_won = any(b[f]["mae_cut_ci"][0] > 0 for f in ["share", "season"])
    card["abstract"] = (
        f"One public-data pipeline for India: IMD rainfall to district flood forecasts, state damage, PMFBY "
        f"crop claims and the protection gap. On unseen monsoons 2013-2020 the district forecast ranks flooded "
        f"districts at AUC {t['auc_model']:.2f} against {t['auc_base']:.2f} for flood history alone. In years with "
        f"reported damage it cuts state errors for {(', '.join(won[:-1]) + ' and ' + won[-1]) if len(won) > 1 else (won[0] if won else 'no damage measure')}. "
        f"It {'improves' if claims_won else 'does not improve'} crop-claim forecasts. {top['state']} has the most "
        f"people at flood risk per rupee of property and crop premium.")
    json.dump(card, open(SITE / "data/india-flood.card.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    readme_table(a, b, c)
    print("  site files written:", len(dist), "districts,", len(years), "test years")
