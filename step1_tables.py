"""Step 1: turn the downloaded files into clean tables in data/clean/.

  districts.csv   641 Census 2011 districts: state, population, households, flood-prone share
  ifi_flood.csv   district x monsoon year: 1 if the India Flood Inventory lists a flood (June-September)
  cwc_damage.csv  state x year flood damage from the Central Water Commission, 1953-2020
  pmfby.csv       state x crop year PMFBY gross premium and paid claims (Rs crore), 2016-17 to 2022-23
  premium.csv     state non-life premium 2024-25 (Rs crore): total and fire (property)

Author: Vivek Mitra
"""
import io
import json
import re

import pandas as pd
import pdfplumber
import shapefile

from common import DATA, CLEAN, RES, TRAIN_END, key, state


def districts():
    r = shapefile.Reader(str(DATA / "maps/2011_Dist.shp"))
    d = pd.DataFrame(r.records(), columns=[f[0] for f in r.fields[1:]])
    d["state"] = d.ST_NM.map(state)
    d.loc[d.DISTRICT == "Data Not Available", "state"] = "Jammu & Kashmir"
    pca = pd.read_csv(DATA / "census/pca-total.csv")
    pca = pca[pca.Level == "DISTRICT"][["State", "District", "TOT_P", "No_HH"]]
    d = d.merge(pca, left_on="censuscode", right_on="District", how="left")
    fa = pd.read_csv(DATA / "ifi/District_FloodedArea.csv")
    fa["k"] = fa.Dist_Name.map(key)
    fa = fa.drop_duplicates("k", keep=False).set_index("k").Corrected_Percent_Flooded_Area
    d["flood_pct"] = d.DISTRICT.map(key).map(fa)
    out = pd.DataFrame({"id": range(len(d)), "district": d.DISTRICT, "state": d.state,
                        "pop": d.TOT_P.fillna(0).astype(int), "households": d.No_HH.fillna(0).astype(int),
                        "flood_pct": d.flood_pct})
    return out


def ifi_flood(dist):
    ev = pd.read_csv(DATA / "ifi/India_Flood_Inventory_v3.csv", encoding="utf-8-sig")
    ev["start"] = pd.to_datetime(ev["Start Date"], dayfirst=True, errors="coerce")
    ev["end"] = pd.to_datetime(ev["End Date"], dayfirst=True, errors="coerce").fillna(ev.start)
    ev = ev[ev.start.notna() & ev.Districts.notna()]
    by_name = {}
    for i, r in dist.iterrows():
        by_name.setdefault(key(r.district), []).append((r.state, r.id))
    hits, names, matched = set(), 0, 0
    for _, e in ev.iterrows():
        # the event counts for every monsoon (1 June - 30 September) its dates overlap; some start
        # dates are typed month-first, e.g. Kerala 2018 is recorded as starting on 8 January
        monsoons = [y for y in range(e.start.year, e.end.year + 1)
                    if e.start <= pd.Timestamp(y, 9, 30) and e.end >= pd.Timestamp(y, 6, 1)]
        if not monsoons:
            continue
        states = {state(s) for s in str(e.State).split(",")} - {None}
        for name in e.Districts.split(","):
            k = key(name)
            names += 1
            cand = by_name.get(k, [])
            if len(cand) > 1:
                cand = [c for c in cand if c[0] in states]
            if len(cand) == 1:
                hits.update((cand[0][1], y) for y in monsoons)
                matched += 1
    print(f"  Inventory district names (monsoon events) matched to Census 2011 districts: {matched}/{names} ({matched / names:.0%})")
    stats = {"ifi_events": int(len(pd.read_csv(DATA / "ifi/India_Flood_Inventory_v3.csv", encoding="utf-8-sig"))),
             "ifi_names": names, "ifi_match": matched / names}
    years = range(1981, 2024)
    rows = [(d, y, int((d, y) in hits)) for d in dist.id for y in years]
    return pd.DataFrame(rows, columns=["id", "year", "flood"]), stats


CWC_ROWS = [0]                  # rows read, reported in the paper
CWC_COLS = ["area_mha", "pop_m", "crop_mha", "crop_cr", "houses", "houses_cr", "cattle", "lives", "public_cr", "total_cr"]


def num(t):
    t = t.replace(",", "").strip("()")
    if t.lower() in ("neg", "nil", "negligible"):
        return 0.0
    try:
        return float(t)
    except ValueError:
        return float("nan")          # NR (not reported), '-' and typos become missing


def cwc_damage():
    """Read each state table by word position, because blank cells shift the plain text."""
    rows = []
    with pdfplumber.open(DATA / "cwc/flood-damage-data-merged.pdf") as pdf:
        for page in pdf.pages[3:]:
            text = (page.extract_text() or "").split("\n")
            st = next(s for s in (state(re.sub(r"TABLE.*", "", l, flags=re.I)) for l in text[:3]) if s)
            lines = {}
            for w in page.extract_words():
                lines.setdefault(round(w["top"] / 3), []).append(w)
            data = []
            for ws in lines.values():
                ws.sort(key=lambda w: w["x0"])
                if len(ws) > 2 and ws[0]["text"].isdigit() and re.fullmatch(r"(19|20)\d\d", ws[1]["text"]):
                    data.append((int(ws[1]["text"]), [((w["x0"] + w["x1"]) / 2, w["text"]) for w in ws[2:]]))
            full = [cells for _, cells in data if len(cells) == 10]
            centres = [sorted(c[i][0] for c in full)[len(full) // 2] for i in range(10)]
            for year, cells in data:
                vals = [float("nan")] * 10
                for x, t in cells:
                    vals[min(range(10), key=lambda i: abs(centres[i] - x))] = num(t)
                rows.append([st, year] + vals)
    d = pd.DataFrame(rows, columns=["state", "year"] + CWC_COLS)
    CWC_ROWS[0] = len(d)
    print(f"  CWC rows read: {len(d)} from {d.state.nunique()} state tables")
    # Telangana is reported inside Andhra Pradesh before 2014, so add the two together.
    return d.groupby(["state", "year"], as_index=False).sum(min_count=1)


def pmfby():
    t = pd.read_html(io.StringIO((DATA / "pmfby/pib_1941399.html").read_text(encoding="utf-8")))[0]
    t.columns = ["name", "premium", "claims"]
    t["name"] = t.name.ffill()                       # merged cells continue the state above
    years, y, rows = list(range(2016, 2023)), 0, []
    for _, r in t.iterrows():
        if r["name"] == "Total" and pd.notna(r.claims):     # blank separator rows are skipped
            total_claims = float(r.claims)
            got = sum(x[3] for x in rows if x[1] == years[y])
            # parsed rows must add up to the printed total (the 2016-17 rows in the source are 0.2% short of it)
            assert abs(got - total_claims) <= 0.005 * total_claims, (years[y], got, total_claims)
            y += 1
        elif state(r["name"]) and pd.notna(r.premium):
            rows.append((state(r["name"]), years[y], float(r.premium), float(r.claims)))
    d = pd.DataFrame(rows, columns=["state", "crop_year", "premium_cr", "claims_cr"])
    return d.groupby(["state", "crop_year"], as_index=False).sum()


# Row order of the yearbook's state tables (Table 2.1.1 and Table 4), checked against the printed totals below.
GIC_ORDER = ["Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
             "Himachal Pradesh", "Jammu & Kashmir", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh",
             "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan",
             "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
             "Andaman & Nicobar", "Chandigarh", "Dadra & Nagar Haveli", "Daman & Diu", "Delhi", "Lakshadweep",
             "Puducherry", "Ladakh"]


def premium():
    """Table 4 (state x class GDPI 2024-25), pages 141-142 of the PDF. Its headers are images, so the
    cells are read by position. Column 1 is Fire (property); the last column is the state total."""
    with pdfplumber.open(DATA / "irdai/GIC_Yearbook_2024-25.pdf") as pdf:
        def grid(i, xs):
            g = {}
            for w in pdf.pages[i].extract_words():
                r = round((w["top"] - 144) / 15.3)
                if w["top"] > 130 and 0 <= r < 38:
                    c = min(range(len(xs)), key=lambda k: abs(xs[k] - w["x0"]))
                    g.setdefault(r, {})[c] = num(w["text"])
            return g
        a = grid(140, [230, 305, 378, 446, 512])
        b = grid(141, [78, 137, 200, 279, 354, 430, 495])
    rows = []
    for r, name in enumerate(GIC_ORDER + ["Total"]):
        cells = [a[r].get(c, float("nan")) for c in range(5)] + [b[r].get(c, float("nan")) for c in range(6)]
        total = b[r][6]
        gap = total - sum(x for x in cells if x == x)
        assert sum(x != x for x in cells) <= 1 and (sum(x != x for x in cells) == 1 or abs(gap) <= 3), (name, cells, total)
        rows.append((name, cells[0] if cells[0] == cells[0] else gap, total))
    d = pd.DataFrame(rows, columns=["name", "fire_cr", "gdpi_cr"])
    assert d.iloc[-1].gdpi_cr == 307633 and d.iloc[-1].fire_cr == 24240     # printed national totals
    d = d.iloc[:-1]
    d["state"] = d.name.map(state)
    return d.groupby("state", as_index=False)[["fire_cr", "gdpi_cr"]].sum()


if __name__ == "__main__":
    CLEAN.mkdir(parents=True, exist_ok=True)
    dist = districts()
    dist.to_csv(CLEAN / "districts.csv", index=False)
    print(f"  districts: {len(dist)}, population {dist['pop'].sum():,}")
    flood, stats = ifi_flood(dist)
    flood.to_csv(CLEAN / "ifi_flood.csv", index=False)
    cwc = cwc_damage()
    cwc.to_csv(CLEAN / "cwc_damage.csv", index=False)
    pmfby().to_csv(CLEAN / "pmfby.csv", index=False)
    prem = premium()
    prem.to_csv(CLEAN / "premium.csv", index=False)
    RES.mkdir(exist_ok=True)
    stats |= {"train_end": TRAIN_END, "districts": len(dist), "districts_populated": int((dist["pop"] > 0).sum()),
              "population": int(dist["pop"].sum()), "cwc_rows": CWC_ROWS[0], "fire_total": float(prem.fire_cr.sum())}
    json.dump(stats, open(RES / "tables.json", "w"), indent=1)
