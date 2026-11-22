"""Check the paper against the results files. Author: Vivek Mitra

1. Every table cell that holds a result equals the value in results/*.json, formatted the same way.
2. Every number in the body text (before the references) is either a formatted result value or one of the
   stated inputs listed in STATED. Anything else fails the check.
"""
import html
import json
import re
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = {k: json.loads((HERE / f"results/{k}.json").read_text()) for k in ["part_a", "part_b", "part_c", "tables"]}

# Stated inputs and method constants that the text may print (they are not results).
STATED = {"0.25", "1.5", "−1.5", "+1.5", "4.5", "0.5", "1.2816", "2.7", "1.0", "1", "80%", "95%", "0.5%", "2,000",
          "2001", "2011", "2012", "2013", "2016", "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026",
          "1953", "1967", "1981", "2010", "2000", "30", "15", "12", "20", "13", "14", "38", "27", "11", "3", "2",
          "4", "5", "6", "7", "8", "9", "10", "0", "24,240", "190", "1.0",
          "29"}                         # 29 May: the Inventory's start date for the Kerala 2018 event


def m(t):
    return t.replace("-", "−") if t.startswith("-") else t


def fmts(v):
    """Every way the paper may print a number from the results."""
    out = set()
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return out
    for d in (0, 1, 2, 3):
        out |= {m(f"{v:.{d}f}"), m(f"{v:,.{d}f}"), "+" + f"{v:.{d}f}", "−" + f"{abs(v):.{d}f}", m(f"{v * 100:.{d}f}") + "%",
                f"{v / 1e6:.{d}f}", f"{round(v):,}"}
    return out


def leaves(x):
    if isinstance(x, dict):
        for v in x.values():
            yield from leaves(v)
    elif isinstance(x, list):
        for v in x:
            yield from leaves(v)
    else:
        yield x


ALLOWED = set(STATED)
for r in R.values():
    for v in leaves(r):
        ALLOWED |= fmts(v)


def docx_parts(path):
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    text = lambda frag: html.unescape("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", frag)))
    tables = [[[text(c) for c in re.findall(r"<w:tc>.*?</w:tc>", row, re.S)] for row in re.findall(r"<w:tr[ >].*?</w:tr>", t, re.S)]
              for t in re.findall(r"<w:tbl>.*?</w:tbl>", xml, re.S)]
    body = re.sub(r"<w:tbl>.*?</w:tbl>", "", xml, flags=re.S)
    paras = [text(p) for p in re.findall(r"<w:p[ >].*?</w:p>", body, re.S)]
    return tables, paras


def main():
    tables, paras = docx_parts(HERE / "paper/india_flood.docx")
    tabs = {t[0][0]: t[1:] for t in tables}
    a1, a2, b, c = R["part_a"]["a1_district"], R["part_a"]["a2_state"], R["part_b"], R["part_c"]
    f2, f3 = (lambda v: m(f"{v:.2f}")), (lambda v: m(f"{v:.3f}"))
    sg = lambda v, f: ("+" if v >= 0 else "−") + f(abs(v))
    ci = lambda a, f: f"[{sg(a[0], f)}, {sg(a[1], f)}]"
    verdict = lambda c_: "better" if c_[0] > 0 else "worse" if c_[1] < 0 else "no clear difference"

    want = []
    for k in ["2013-2020", "2021-2023"]:
        r = a1[k]
        want += [[f"AUC, {k}", f3(r["auc_model"]), f3(r["auc_base"]), f"{sg(r['auc_gain'], f3)} {ci(r['auc_gain_ci'], f3)}", verdict(r["auc_gain_ci"])],
                 [f"Log loss, {k}", f3(r["logloss_model"]), f3(r["logloss_base"]), f"{sg(r['logloss_cut'], f3)} {ci(r['logloss_cut_ci'], f3)}", verdict(r["logloss_cut_ci"])]]
    assert tabs["Measure (held-out)"] == want, (tabs["Measure (held-out)"], want)

    rows = tabs["Measure"]
    for row, (t, r) in zip(rows, a2.items()):
        assert row[2:6] == [f3(r["mae_model"]), f3(r["mae_base"]), f"{sg(r['mae_cut'], f2)} {ci(r['mae_cut_ci'], f2)}", verdict(r["mae_cut_ci"])], row

    for row, f in zip(tabs["Feature"], ["share", "season"]):
        r = b[f]
        assert row[1:5] == [m(f"{r['mae_model']:.4f}"), m(f"{r['mae_base']:.4f}"), f"{sg(r['mae_cut'], f3)} {ci(r['mae_cut_ci'], f3)}", verdict(r["mae_cut_ci"])], row

    cv = R["part_a"]["training_cv"]["a2_features"]
    for row in tabs["Training error (log)"]:
        assert row[1:] == [f3(cv[t][row[0]]) for t in ["people", "houses", "crop_ha", "lives"]], row

    for row, r in zip(tabs["State"], c["states"]):
        assert row[0] == r["state"] and row[4] == f"{round(r['gap']):,}", (row, r)

    for row, e in zip(tabs["Event"], R["part_a"]["events"]):
        assert row[1] == f"{e['flooded']} of {e['districts']}" and row[2] == f"{e['expected']:.1f}", (row, e)

    text = " ".join(paras[: next(i for i, p in enumerate(paras) if p.strip() == "References")])
    nums = re.findall(r"(?<![A-Za-z\d])[−+]?\d[\d,]*\.?\d*%?", text)       # not digits inside names or links
    bad = sorted({n.rstrip(".,") for n in nums} - ALLOWED - {n.rstrip(".,").lstrip("+") for n in nums if n.lstrip("+") in ALLOWED})
    bad = [n for n in bad if n not in ALLOWED and n.lstrip("+−") not in ALLOWED]
    assert not bad, f"numbers in the text that are not in the results or the stated inputs: {bad}"
    print(f"  ok  paper matches results: 6 tables checked, {len(nums)} numbers in the text all traced")


if __name__ == "__main__":
    main()
