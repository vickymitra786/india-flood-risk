// Builds paper/india_flood.docx from ../results/*.json and paper/figures/*.png.
// Author: Vivek Mitra. Every number in the text is read from the results files; verdict words come from the intervals.
const fs = require("fs");
const path = require("path");
const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell, WidthType,
  ImageRun, Footer, PageNumber, BorderStyle, ShadingType } = require("docx");

const rd = f => JSON.parse(fs.readFileSync(path.join(__dirname, "..", "results", f), "utf8"));
const A = rd("part_a.json"), Bp = rd("part_b.json"), C = rd("part_c.json"), T = rd("tables.json");
const A1 = A.a1_district, A2 = A.a2_state, E = A.events;
const P0 = A1["2013-2020"], P1 = A1["2021-2023"];

const minus = t => t.replace(/^-/, "−");
const f4 = v => minus(v.toFixed(4)), f3 = v => minus(v.toFixed(3)), f2 = v => minus(v.toFixed(2)), f1 = v => minus(v.toFixed(1));
const sg = (v, f) => (v >= 0 ? "+" : "−") + f(Math.abs(v));
const int = v => Math.round(v).toLocaleString("en-US");
const big = v => v >= 1e6 ? (v / 1e6).toFixed(1) + " million" : int(v);
const mil = v => (v / 1e6).toFixed(1) + " million";
const pc = v => (v * 100).toFixed(0) + "%";
const ci = (a, f) => `[${sg(a[0], f)}, ${sg(a[1], f)}]`;
const better = c => c[0] > 0, worse = c => c[1] < 0;
const verdict = c => better(c) ? "better" : worse(c) ? "worse" : "no clear difference";
const NAMES = { people: "people affected", houses: "houses damaged", crop_ha: "crop area hit (ha)", lives: "lives lost" };
const wonA2 = Object.keys(A2).filter(t => better(A2[t].mae_cut_ci)), tieA2 = Object.keys(A2).filter(t => !better(A2[t].mae_cut_ci));
const list = a => a.length < 2 ? a.join("") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1];
const claimsWon = ["share", "season"].filter(f => better(Bp[f].mae_cut_ci));
const topS = C.states[0], top3 = C.states.slice(0, 3);
const CV = A.training_cv, CAND = Object.keys(CV.a2_features.people);
const shareBest = Object.values(CV.a2_features).every(r => Object.entries(r).every(([k, v]) => k === "share" || v >= r.share));

// ---------- docx helpers ----------
const FONT = "Calibri";
const run = (t, o = {}) => new TextRun({ text: t, font: FONT, size: 22, ...o });
const kids = parts => (Array.isArray(parts) ? parts : [parts]).map(x => (typeof x === "string" ? run(x) : x));
const para = parts => new Paragraph({ children: kids(parts), spacing: { after: 120, line: 276 } });
const b = t => run(t, { bold: true }), i = t => run(t, { italics: true });
const H1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 280, after: 120 }, children: [run(t, { bold: true, size: 28, color: "1F4E8C" })] });
const H2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 80 }, children: [run(t, { bold: true, size: 24 })] });
const bullet = parts => new Paragraph({ bullet: { level: 0 }, spacing: { after: 60 }, children: kids(parts) });
const caption = t => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [run(t, { italics: true, size: 19 })] });
const figure = (file, w, h, cap) => [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 80 }, keepNext: true,
  children: [new ImageRun({ type: "png", data: fs.readFileSync(path.join(__dirname, "figures", file)), transformation: { width: w, height: h } })] }), caption(cap)];
const line = { style: BorderStyle.SINGLE, size: 4, color: "BFC5CE" }, none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
function table(head, rows, widths) {
  const tot = widths.reduce((a, x) => a + x, 0);
  const cell = (t, hdr, k) => new TableCell({
    width: { size: Math.round(widths[k] / tot * 100), type: WidthType.PERCENTAGE },
    shading: hdr ? { type: ShadingType.CLEAR, color: "auto", fill: "EEF2F7" } : undefined,
    borders: { top: line, bottom: line, left: none, right: none }, margins: { top: 40, bottom: 40, left: 80, right: 80 },
    children: [new Paragraph({ alignment: k ? AlignmentType.RIGHT : AlignmentType.LEFT, children: [run(String(t), { size: 18, bold: hdr })] })],
  });
  return new Table({ width: { size: 100, type: WidthType.PERCENTAGE },
    rows: [new TableRow({ tableHeader: true, cantSplit: true, children: head.map((t, k) => cell(t, true, k)) }),
      ...rows.map(r => new TableRow({ cantSplit: true, children: r.map((t, k) => cell(t, false, k)) }))] });
}

// ---------- content ----------
const abstract = `Insurers in India need three things from a flood model: which districts a monsoon will flood, how much damage follows, and where flood cover is thin. This paper builds one pipeline for all three from public data. It uses IMD daily gridded rainfall, the India Flood Inventory, Central Water Commission damage tables, PMFBY crop-insurance figures, state premium from the General Insurance Council and the 2011 Census. Every model is fitted on monsoons up to ${T.train_end} and scored once on later years against a simple baseline. A logistic regression on each district's flood history and two rainfall ratios ranks flooded districts in 2013-2020 at AUC ${f3(P0.auc_model)}, against ${f3(P0.auc_base)} for flood history alone (gain ${sg(P0.auc_gain, f3)}, 95% interval ${ci(P0.auc_gain_ci, f3)}). ${better(P1.auc_gain_ci) ? "The gain holds" : "The gain is not clear"} in 2021-2023 (${sg(P1.auc_gain, f3)}, ${ci(P1.auc_gain_ci, f3)}). In state-years with reported damage, the population-weighted district forecast reduces the error for ${wonA2.length ? list(wonA2.map(t => NAMES[t].replace(" (ha)", ""))) : "no damage measure"}${tieA2.length ? `, with no clear difference for ${list(tieA2.map(t => NAMES[t].replace(" (ha)", "")))}` : ""}. ${claimsWon.length ? "Rainfall measures improve" : "Neither the flood forecast nor the monsoon total improves"} held-out forecasts of PMFBY claims, which are public only by state and year. Measured as people at flood risk per ₹1 crore of fire and PMFBY premium, the protection gap is widest in ${list(top3.map(r => r.state))}. Two commands reproduce every number.`;

const srcRows = [
  ["IMD 0.25° daily gridded rainfall [2]", "1981-2023", "rainfall features"],
  ["India Flood Inventory v3 [1]", "1981-2023 monsoons", "flooded districts (A)"],
  ["CWC flood damage statistics [4]", "2001-2020", "state damage (A)"],
  ["PIB: PMFBY premium and claims [5]", "2016-17 to 2021-22", "crop claims (B, C)"],
  ["GI Council yearbook 2024-25 [6]", "2024-25", "fire premium (C)"],
  ["Census 2011 Primary Census Abstract [7]", "2011", "population (A, C)"],
  ["DataMeet India maps [8]", "Census 2011", "districts, official outline"],
];

const a1Rows = [];
for (const [k, r] of [["2013-2020", P0], ["2021-2023", P1]]) {
  a1Rows.push([`AUC, ${k}`, f3(r.auc_model), f3(r.auc_base), `${sg(r.auc_gain, f3)} ${ci(r.auc_gain_ci, f3)}`, verdict(r.auc_gain_ci)]);
  a1Rows.push([`Log loss, ${k}`, f3(r.logloss_model), f3(r.logloss_base), `${sg(r.logloss_cut, f3)} ${ci(r.logloss_cut_ci, f3)}`, verdict(r.logloss_cut_ci)]);
}
const a2Rows = Object.entries(A2).map(([t, r]) => [NAMES[t], `${r.n_train} / ${r.n_test}`, f3(r.mae_model), f3(r.mae_base),
  `${sg(r.mae_cut, f2)} ${ci(r.mae_cut_ci, f2)}`, verdict(r.mae_cut_ci), `${pc(r.cover80_model)} / ${pc(r.cover80_base)}`]);
const a2Slope = Object.entries(A2).map(([t, r]) => `${NAMES[t].replace(" (ha)", "")} ${f2(r.slope)} (s.e. ${f2(r.slope_se)})`);
const evRows = E.map(e => {
  const m = e.people ? "people" : e.houses ? "houses" : null, v = m && e[m];
  return [`${e.state} ${e.year}`, `${e.flooded} of ${e.districts}`, f1(e.expected), f1(e.expected_history),
    m ? NAMES[m] : "–", v ? big(v.actual) : "–", v ? `${big(v.model)} [${big(v.lo)}, ${big(v.hi)}]` : "–", v ? big(v.base) : "–"];
});
const bRows = [["share", "flood share from Part A"], ["season", "monsoon total vs normal"]].map(([f, lab]) => {
  const r = Bp[f];
  return [lab, f4(r.mae_model), f4(r.mae_base), `${sg(r.mae_cut, f3)} ${ci(r.mae_cut_ci, f3)}`, verdict(r.mae_cut_ci), `${f2(r.slope)} (${f2(r.slope_se)})`];
});
const cRows = C.states.slice(0, 12).map(r => [r.state, mil(r.at_risk), int(r.fire_cr), int(r.crop_cr), int(r.gap)]);
const topD = C.top20_districts;
const topDStates = [...new Set(topD.map(r => r.state))];

const children = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [run("Flood risk, crop-insurance claims and the protection gap in India: an integrated district-level model on public data", { bold: true, size: 32, color: "1F4E8C" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [run("Vivek Mitra", { size: 24 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [run("Independent researcher, vivekmitra.com", { size: 20, color: "5A6472" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 }, children: [run("November 2026", { size: 20, color: "5A6472" })] }),
  H1("Abstract"), para(abstract),
  para([b("Keywords: "), run("flood risk, India, monsoon, catastrophe model, crop insurance, PMFBY, protection gap, logistic regression, temporal validation")]),

  H1("1. Introduction"),
  para("Floods recur in India every monsoon. An insurer, a reinsurer or a public agency planning flood cover needs answers at the level where people live: which districts are likely to flood in a given monsoon, how large the damage will be when they do, how crop-insurance claims respond, and where flood risk is high but cover is low."),
  para("India has the public data to start on each question, but in separate places. The India Meteorological Department publishes daily gridded rainfall [2]. The India Flood Inventory lists flood events with the districts they hit [1]. The Central Water Commission (CWC) compiles state damage tables [4]. Government releases give state figures for the Pradhan Mantri Fasal Bima Yojana (PMFBY) crop-insurance scheme [5], and the General Insurance Council publishes premium by state [6]. This paper joins them in one district table and one pipeline, and asks what each link can and cannot support."),
  para("The method is deliberately simple. Each part uses the simplest model that can be explained in a sentence and is kept only if it beats a simple baseline on years it never saw. The contributions are:"),
  bullet([b("A district flood forecast tested on unseen monsoons. "), run("A logistic regression on flood history and two rainfall ratios, fitted on 1981-" + T.train_end + " and scored on 2013-2020 and 2021-2023 separately.")]),
  bullet([b("An honest link from rainfall to reported damage. "), run("The district forecast is aggregated to states and tested against CWC damage. The paper reports where it helps and where it does not.")]),
  bullet([b("A test of crop-insurance claims. "), run("PMFBY claims are compared with the flood forecast and the monsoon total.")]),
  bullet([b("A protection-gap ranking. "), run("People at flood risk per rupee of property and crop premium, by state and by district, with every input public.")]),

  H1("2. Data"),
  para("All inputs are public and downloaded by a script, without keys or logins. Table 1 lists them."),
  table(["Source", "Years used", "Used for"], srcRows, [3, 2, 2]),
  caption("Table 1. Data sources."),
  H2("2.1 Districts and population"),
  para(`The unit is the ${T.districts_populated} districts of Census 2011, taken from the DataMeet Census 2011 district map [8]. That map follows India's official boundaries, including all of Jammu & Kashmir, Ladakh and Arunachal Pradesh. One further polygon in Jammu & Kashmir has no census data and is shown but not modelled. Population comes from the Census 2011 Primary Census Abstract [7]. The census districts add up to ${int(T.population)} people.`),
  H2("2.2 Rainfall"),
  para("IMD's gridded product interpolates rain-gauge readings to a 0.25° grid of daily totals [2]. It was downloaded year by year with the request used by the open-source imdlib package [3]. Each district averages the grid cells whose centres fall inside it. A district too small to contain a cell centre uses the nearest cell. For each monsoon (1 June to 30 September) two numbers are kept: the wettest three consecutive days (rx3, in mm) and the season total."),
  H2("2.3 Flood record"),
  para(`The India Flood Inventory [1] lists ${int(T.ifi_events)} flood events from 1967 to 2023, mostly from IMD's disastrous-weather reports, each with the districts it affected. A district-year is marked flooded if the district is named by any event whose dates overlap that year's monsoon (1 June to 30 September). Inventory names were matched to census names within the listed states. ${pc(T.ifi_match)} of the ${int(T.ifi_names)} district mentions matched. The rest are mostly districts created after 2011 and are dropped. The Inventory records many more events from 2021 onwards (Section 6), so 2021-2023 are scored separately.`),
  H2("2.4 Damage, claims and premium"),
  para(`The CWC tables [4] give, for each state and year from 1953 to 2020, people affected, crop area hit, houses damaged, lives lost and damage in rupees. They were read from the PDF by cell position, giving ${int(T.cwc_rows)} state-year rows. "Neg" and "Nil" are read as zero and "NR" (not reported) as missing. Telangana is added to Andhra Pradesh and Ladakh to Jammu & Kashmir, as the tables do for most years. The PMFBY table [5] gives gross premium and paid claims by state and crop year from 2016-17. The parsed rows match the printed yearly totals to within 0.5%. 2022-23 is left out because its claims were still being settled. State fire premium for 2024-25 comes from the General Insurance Council yearbook [6]. Each parsed row adds up to the printed state total, and the column adds up to the printed national fire premium of ₹${int(T.fire_total)} crore.`),

  H1("3. Method"),
  H2("3.1 Rainfall features"),
  para(`For each district, the normal of rx3 and of the season total is the median over 1981-2010. The two features are the logs of the ratios to these normals: r3 = log(rx3 / normal rx3) and s = log(total / normal total), each limited to between −1.5 and +1.5 (a factor of about 4.5). The limit stops desert districts with tiny normals from producing extreme values. It was chosen by leave-one-year-out cross-validation within the training years only, where it ${CV.clip.clipped < CV.clip.unclipped ? "lowered" : "did not lower"} the log loss from ${f3(CV.clip.unclipped)} to ${f3(CV.clip.clipped)}.`),
  H2("3.2 Part A: district flood chance"),
  para("The chance p that a district floods in a monsoon is a logistic regression: log(p / (1 − p)) = b0 + b1·h + b2·r3 + b3·s. Here h is the log-odds of the district's own flood rate in the training years, smoothed as (floods + 0.5) / (years + 1). For a training row, h leaves out that row's own year, so the model never sees its own answer. The baseline is the smoothed flood rate alone. The model is fitted on all district-years from 1981 to " + T.train_end + " with statsmodels [9]. Ranking is scored by the area under the ROC curve (AUC) [10] and probabilities by the log loss."),
  H2("3.3 Part A: state damage"),
  para("For each state and year, share is the population-weighted average of the district chances p: the expected share of the state's people living in districts that flood. Many CWC state-years are zero or blank, often because nothing was reported, so the model answers a narrower question: in a year when the state reports damage, how large is it? For each of four measures, log(damage) = a(state) + b·share, fitted by ordinary least squares on 2001-" + T.train_end + " and tested on 2013-2020. The series starts in 2001 so that the three states formed in 2000 are reported on their own throughout, and a state needs at least five reported training years. The baseline is the state's own average log damage. The 80% range is the forecast ± 1.2816 residual standard deviations."),
  para(`The state feature was chosen within the training years from five candidates, by leave-one-year-out error (Table 2): share; the log of the expected number of flooded districts; the population-weighted mean of r3; the means of r3 and of s together; and the largest r3 in the state. ${shareBest ? "Share had the lowest error for all four measures" : "Share was kept because it links the district forecast to damage; it was not the lowest-error candidate for every measure"}.`),
  table(["Training error (log)", ...Object.keys(NAMES).map(t => NAMES[t].replace(" (ha)", ""))],
    CAND.map(c => [c, ...Object.keys(NAMES).map(t => f3(CV.a2_features[t][c]))]), [3, 2, 2, 2, 2]),
  caption("Table 2. Choosing the state feature: mean absolute log error, leaving out one training year (2001-" + T.train_end + ") at a time. No test year is used."),
  H2("3.4 Part B: crop-insurance claims"),
  para("For each state and crop year, log(claims / premium) = c(state) + g·x, where x is either share from Part A or the population-weighted s (the monsoon total vs normal, which also captures drought). The baseline is the state's own average loss ratio. With only six crop years, each year is left out in turn and predicted from the other five."),
  H2("3.5 Part C: protection gap"),
  para("People at flood risk in a district = the district's chance p averaged over the 1981-2023 monsoons × its population. Flood-relevant premium for a state = fire (property) premium for 2024-25 + average PMFBY premium for 2019-20 to 2021-22. The gap is people at flood risk per ₹1 crore of that premium. No district premium is published, so a district receives its state's premium in proportion to population. Rupee loss is not used, because the CWC rupee series is too incomplete. For example, Maharashtra reports no rupee damage for 2011-2020."),
  H2("3.6 Uncertainty"),
  para("Every gain is the observed difference between model and baseline on the held-out rows. Its 95% interval comes from a paired bootstrap with 2,000 resamples [11]. Whole districts (for the district forecast) or whole states (for state damage and for claims) are resampled, and both models are scored on the same resample. A model is called better only when the whole interval is above zero."),

  H1("4. Results"),
  H2("4.1 Which districts flood"),
  para(`The fitted coefficients are b1 = ${f2(A1.coef.history)} (s.e. ${f2(A1.coef_se.history)}) for history, b2 = ${f2(A1.coef.r3)} (${f2(A1.coef_se.r3)}) for the 3-day ratio and b3 = ${f2(A1.coef.season)} (${f2(A1.coef_se.season)}) for the season ratio, from ${int(A1.n_train)} training district-years. Table 3 scores the model on unseen years. In 2013-2020, ${pc(P0.flooded_share)} of ${int(P0.n)} district-years flooded. The model ranks them at AUC ${f3(P0.auc_model)} against ${f3(P0.auc_base)} for history alone, and the gain is ${verdict(P0.auc_gain_ci) === "better" ? "clear of zero" : "not clear of zero"}. The log-loss gain is ${verdict(P0.logloss_cut_ci) === "better" ? "also clear of zero" : "not clear of zero"} (${sg(P0.logloss_cut, f3)}, ${ci(P0.logloss_cut_ci, f3)}). In 2021-2023, when the Inventory records more floods (${pc(P1.flooded_share)} of district-years), the ranking gain is ${sg(P1.auc_gain, f3)} ${ci(P1.auc_gain_ci, f3)}.`),
  table(["Measure (held-out)", "Model", "History only", "Gain [95% interval]", "Verdict"], a1Rows, [3, 1, 1, 3, 2]),
  caption("Table 3. Part A, district flood forecast on unseen monsoons. For log loss the gain is the reduction."),
  ...figure("map.png", 430, 458, "Figure 1. Average district flood chance per monsoon, 1981-2023, with the official India outline. Orange outlines: the 20 districts with the widest protection gap (Section 4.4). Grey: no census or rainfall data."),
  para("Table 4 shows named floods in the test years. \"Expected\" is the sum of the district chances with the real rainfall, and \"history\" is the same sum from flood rates alone. The damage columns show one CWC measure the state reported that year: people affected where reported, otherwise houses damaged."),
  table(["Event", "Districts flooded", "Expected", "History", "CWC measure", "Reported", "Forecast [80% range]", "State average"], evRows, [2, 2, 1, 1, 2, 2, 3, 2]),
  caption("Table 4. Named floods in the test years. The CWC series ends in 2020, so Himachal Pradesh 2023 has district counts only."),
  para("An earlier version of the flood record counted an event only if it started between June and September. This named-event check showed that it missed Kerala 2018: the Inventory gives the main event a start date of 29 May, and a second event a start date typed month-first as 8 January. The record was then changed to count any event whose dates overlap June to September. This corrects the record, not the model, and every result in this paper uses the corrected record."),
  H2("4.2 How much damage"),
  para(`Table 5 compares the state damage model with the state average on 2013-2020. Errors are mean absolute differences in natural logs, so 1.0 means a typical miss by a factor of about 2.7. The model is better for ${wonA2.length ? list(wonA2.map(t => NAMES[t].replace(" (ha)", ""))) : "none of the four measures"}${tieA2.length ? `. For ${list(tieA2.map(t => NAMES[t].replace(" (ha)", "")))} the interval includes zero, so there is no clear difference` : ""}. The fitted slopes on share are ${list(a2Slope)}. The 80% ranges hold fewer than 80% of the outcomes (last column), so they are too narrow.`),
  table(["Measure", "Train / test", "Model", "State average", "Gain [95% interval]", "Verdict", "In 80% range"], a2Rows, [3, 2, 1, 1, 3, 2, 2]),
  caption("Table 5. Part A, state damage in years with reported damage, 2013-2020. Mean absolute error of log damage. Gains are computed from unrounded errors. Last column: model / baseline."),
  ...figure("damage.png", 430, 264, "Figure 2. Houses damaged by state and year, 2013-2020: forecast (blue, with 80% range) and state average (grey) against the reported figure. Log scales."),
  H2("4.3 Crop-insurance claims"),
  para(`Table 6 tests ${Bp.n} state-years in ${Bp.states} states (crop years ${Bp.years[0]}-${String(Bp.years[0] + 1).slice(2)} to ${Bp.years[1]}-${String(Bp.years[1] + 1).slice(2)}, ${Bp.zero_claim_rows_dropped} rows with zero claims dropped). ${claimsWon.length ? "A rainfall measure beats the state's usual loss ratio." : "Neither measure beats the state's usual loss ratio on the left-out years."} The monsoon-total slope is ${f2(Bp.season.slope)} (s.e. ${f2(Bp.season.slope_se)}, p = ${f2(Bp.season.slope_p)} in the fit to all six years): the sign means a drier monsoon goes with higher claims, but the slope does not improve forecasts of left-out years. The flood-share slope is ${f2(Bp.share.slope)} (s.e. ${f2(Bp.share.slope_se)}). With state-year data only, the flood signal in crop claims cannot be separated from drought, pests and scheme rules.`),
  table(["Feature", "Model", "State average", "Gain [95% interval]", "Verdict", "Slope (s.e.)"], bRows, [3, 1, 1, 3, 2, 2]),
  caption("Table 6. Part B, mean absolute error of log(claims / premium), each crop year left out in turn. Gains are computed from unrounded errors."),
  H2("4.4 Protection gap"),
  para(`Across the states with a premium figure, about ${mil(C.national.at_risk)} people live in districts expected to flood in an average monsoon, against ₹${int(C.national.premium_cr)} crore of fire and PMFBY premium: ${int(C.national.gap)} people per ₹1 crore. Table 7 ranks the states. ${topS.state} leads with ${mil(topS.at_risk)} people at risk against ₹${int(topS.premium_cr)} crore of premium${topS.crop_cr === 0 ? ", with no PMFBY premium in 2019-20 to 2021-22" : ""}. ${topDStates.length === 1 ? `All 20 districts with the widest gap are in ${topDStates[0]}, led by ${list(topD.slice(0, 3).map(r => r.district))}, because districts inherit their state's cover.` : `The 20 districts with the widest gap are in ${list(topDStates)}.`}`),
  table(["State", "People at risk", "Fire, ₹ cr", "PMFBY, ₹ cr", "People per ₹1 cr"], cRows, [3, 2, 1, 1, 2]),
  caption("Table 7. Part C, the 12 states with the widest protection gap."),
  ...figure("gap.png", 430, 291, "Figure 3. People at flood risk per ₹1 crore of fire and PMFBY premium, top 15 states."),

  H1("5. Discussion"),
  para("The rainfall link adds a real but modest amount to what history already says. Flood history explains most of the ranking: districts that flooded before tend to flood again. Rainfall then moves a district's chance up or down from one monsoon to the next. That is the useful part for an insurer, because a what-if such as a 30% heavier monsoon in one state moves the forecast through coefficients that were tested on unseen years. Rainfall far outside the observed range is still an extrapolation."),
  para("The weaker links are as informative as the strong one. Reported state damage is so incomplete that a rainfall-driven model can only size damage in years when damage is reported. Crop claims respond to the monsoon as a whole, mostly through drought, rather than to flood risk. The protection gap therefore uses people at risk instead of rupee losses."),

  H1("6. Limitations"),
  bullet("The flood record is a list of reported events, not a measured flood extent. A district with no report may still have flooded. Reporting rose sharply from 2021, which is why those years are scored separately."),
  bullet("The district forecast is for the June-September monsoon. North-east monsoon floods in Tamil Nadu and nearby states (October-December) are outside it."),
  bullet("The damage intervals hold fewer than their stated 80% of outcomes, so true uncertainty is wider. CWC figures are state reports compiled without a common method."),
  bullet("Claims are public only by state and crop year, with Kharif and Rabi combined, for six mature years."),
  bullet("The premium side of the gap uses 2024-25 fire premium, which covers more perils than flood and may be booked where a policy is issued rather than where the property is. District premium is assigned by population."),
  bullet("The India Flood Inventory is licensed CC BY-NC 4.0, so this work is for non-commercial research. A commercial use needs the data owners' permission."),
  bullet("Districts are those of Census 2011. Newer districts are counted inside their 2011 parents, and Inventory mentions of new district names are dropped."),

  H1("7. Reproducibility"),
  para("The code is public under the GNU AGPL-3.0 at github.com/vickymitra786/india-flood-risk. Two commands rebuild everything: python get_data.py downloads the public inputs, and python run_all.py writes the cleaned tables, the results, the website data, the figures and this paper. A check script confirms that the fitted logistic regression has a zero score, that least squares meets its normal equations, that AUC by ranks equals the pair count, and that the formula in the web page gives the same probabilities as Python. A second script checks that the numbers in this paper's tables match the results files. The live demo is at vivekmitra.com/india-flood.html."),
  para("Funding and interests: no funding; no competing interests. Data availability: all inputs are public and are downloaded by the released script; the India Flood Inventory is CC BY-NC 4.0 and is not redistributed."),

  H1("References"),
  ...[
    "[1] Saharia, M., Jain, A., Baishya, R.R., Haobam, S., Sreejith, O.P., Pai, D.S., Rafieeinasab, A. (2021). India flood inventory: creation of a multi-source national geospatial database to facilitate comprehensive flood research. Natural Hazards 108, 619-633. https://doi.org/10.1007/s11069-021-04698-6. Data: Zenodo, https://doi.org/10.5281/zenodo.4742142.",
    "[2] Pai, D.S., Sridhar, L., Rajeevan, M., Sreejith, O.P., Satbhai, N.S., Mukhopadhyay, B. (2014). Development of a new high spatial resolution (0.25° × 0.25°) long period (1901-2010) daily gridded rainfall data set over India and its comparison with existing data sets over the region. Mausam 65(1), 1-18.",
    "[3] imdlib: a Python library for IMD gridded meteorological data. https://github.com/iamsaswata/imdlib.",
    "[4] Central Water Commission (2022). Flood damage statistics (state-wise and for the country as a whole) during 1953 to 2020. New Delhi. https://cwc.gov.in/sites/default/files/flood-damage-data-merged.pdf.",
    "[5] Press Information Bureau, Government of India (2023). Premium collection and insurance claims under Pradhan Mantri Fasal Bima Yojana. Release ID 1941399. https://www.pib.gov.in/PressReleasePage.aspx?PRID=1941399.",
    "[6] General Insurance Council (2025). Indian Non-Life Insurance Industry Yearbook 2024-25. Mumbai. https://www.gicouncil.in/Year-Book/GIC_Yearbook_2024-25.pdf.",
    "[7] Office of the Registrar General & Census Commissioner, India (2013). Primary Census Abstract, Census of India 2011. District tables as scraped in https://github.com/pigshell/india-census-2011.",
    "[8] DataMeet (2019). Community created maps of India: Census 2011 district boundaries and India composite boundary. https://github.com/datameet/maps. CC BY 4.0.",
    "[9] Seabold, S., Perktold, J. (2010). statsmodels: econometric and statistical modeling with Python. Proceedings of the 9th Python in Science Conference, 92-96.",
    "[10] Hanley, J.A., McNeil, B.J. (1982). The meaning and use of the area under a receiver operating characteristic (ROC) curve. Radiology 143(1), 29-36.",
    "[11] Efron, B., Tibshirani, R.J. (1993). An Introduction to the Bootstrap. Chapman & Hall, New York.",
  ].map(t => new Paragraph({ spacing: { after: 80 }, children: [run(t, { size: 20 })] })),
];

const doc = new Document({
  creator: "Vivek Mitra", title: "Flood risk, crop-insurance claims and the protection gap in India", description: "Vivek Mitra, vivekmitra.com",
  styles: { default: { document: { run: { font: FONT, size: 22 } } } },
  sections: [{
    properties: { page: { margin: { top: 1200, bottom: 1200, left: 1200, right: 1200 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [run("Vivek Mitra · India flood risk · page ", { size: 16, color: "5A6472" }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "5A6472", font: FONT })] })] }) },
    children,
  }],
});
Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(path.join(__dirname, "india_flood.docx"), buf);
  console.log("  wrote paper/india_flood.docx");
});
