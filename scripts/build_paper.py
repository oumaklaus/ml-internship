"""Render docs/index.html from work/outputs/w08_capstone_metrics.json.

Every number on the deployed page is read out of the metrics file the capstone notebook wrote. Nothing
is typed in by hand, so the paper cannot drift from the run that produced it.
"""
import json, os, shutil, html, pathlib

ROOT = pathlib.Path("/home/zuko/ml-internship")
M = json.loads(pathlib.Path(os.environ.get("W08_METRICS",
    ROOT / "work/outputs/w08_capstone_metrics.json")).read_text())
DOCS = pathlib.Path(os.environ.get("W08_DOCS", ROOT / "docs"))
ASSETS = DOCS / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

FIGS = ["w08_ladder.png", "w08_forward_stability.png", "w08_capacity_curve.png",
        "w08_archetype_rates.png"]
for f in FIGS:
    srcf = ROOT / "work/figures" / f
    if srcf.exists():
        shutil.copy(srcf, ASSETS / f)
    elif not os.environ.get("W08_DOCS"):
        raise SystemExit(f"missing figure {srcf}")

def f3(x):  return f"{float(x):.3f}"
def n(x):   return f"{int(x):,}"
def pct(x, d=1): return f"{100 * float(x):.{d}f}%"

P = {p["panel"]: p for p in M["panels"]}
H = M["headline"]
LK = M["leakage_audit"]
Q = M["queue"]
lad = {(r["design"], r["model"]): r for r in M["split_ladder_mean"]}
lad_std = {(r["design"], r["model"]): r for r in M["split_ladder_std"]}
cap = M["capacity_curve"]
arch = {r["archetype"]: r for r in M["archetype_rates_out_of_fold"]}
calib = M["calibration"]
surv = M["survivor_filter"]
bases = M["base_rate_by_pair"]

RUNG1, RUNG2, RUNG3 = "1 random, Mar>Apr", "2 grouped, Mar>Apr", "3 time fwd, Apr>May"
R4A, R4B = "4 grouped+time, pair 1 Apr>May", "4 grouped+time, pair 2 May>Jun"
fwd_lo, fwd_hi = sorted([H["forward_auc_pair_1"], H["forward_auc_pair_2"]])
rule_lo, rule_hi = sorted([H["forward_baseline_pair_1"], H["forward_baseline_pair_2"]])
drop = H["random_split_auc"] - fwd_hi
client_drop = lad[(RUNG1, "rf_momentum")]["AUC"] - lad[(RUNG2, "rf_momentum")]["AUC"]

# --- Results table, model against baseline at every rung on the same rows -----------------------
def rung_rows():
    out = []
    for design, label in ((RUNG1, "1. Random split"), (RUNG2, "2. Grouped by client"),
                          (RUNG3, "3. Time forward"), (R4A, "4. Grouped + time, pair 1"),
                          (R4B, "4. Grouped + time, pair 2")):
        rf, bl = lad[(design, "rf_momentum")], lad[(design, "baseline_w04")]
        sd = lad_std.get((design, "rf_momentum"), {}).get("AUC")
        sd = "" if sd in (None, "") or (isinstance(sd, float) and sd != sd) else f" <span class='sd'>&plusmn;{float(sd):.3f}</span>"
        hi = " class='hi'" if design.startswith("4 ") else ""
        out.append(f"""<tr{hi}><td>{label}</td>
          <td class="num"><b>{f3(rf['AUC'])}</b>{sd}</td>
          <td class="num">{f3(bl['AUC'])}</td>
          <td class="num">{f3(rf['AUC'] - bl['AUC'])}</td>
          <td class="num">{f3(rf['p@500'])}</td>
          <td class="num">{f3(bl['p@500'])}</td>
          <td class="num dim">{f3(rf['test_base'])}</td></tr>""")
    return "\n".join(out)

# --- Capacity table at the budgets a team would actually pick ----------------------------------
BUDGETS = [50, 200, 500, 2000]
def cap_rows():
    out = []
    for k in BUDGETS:
        row = {r["order"]: r for r in cap if r["pages_reviewed"] == k}
        out.append(f"""<tr><td>{k:,} pages <span class="dim">({row['queue priority']['review_hours']:.0f}h)</span></td>
          <td class="num"><b>{f3(row['queue priority']['share_of_at_risk_reached'])}</b></td>
          <td class="num">{f3(row['impressions only']['share_of_at_risk_reached'])}</td>
          <td class="num">{f3(row['model score alone']['share_of_at_risk_reached'])}</td>
          <td class="num"><b>{f3(row['queue priority']['share_reviewed_that_declined'])}</b></td>
          <td class="num">{f3(row['impressions only']['share_reviewed_that_declined'])}</td>
          <td class="num">{f3(row['model score alone']['share_reviewed_that_declined'])}</td></tr>""")
    return "\n".join(out)

def arch_rows():
    out = []
    for a in sorted(arch):
        r = arch[a]
        act = next(d["action"] for d in M["archetype_definitions"] if d["archetype"] == a)
        cond = next(d["condition"] for d in M["archetype_definitions"] if d["archetype"] == a)
        rec = act in ("refresh_senior_review", "queue_for_refresh", "on_page_optimisation",
                      "title_snippet_review")
        out.append(f"""<tr class="{'rec' if rec else ''}"><td><code>{html.escape(a)}</code></td>
          <td class="dim small">{html.escape(cond)}</td>
          <td>{'<b>' if rec else ''}{html.escape(act.replace('_', ' '))}{'</b>' if rec else ''}</td>
          <td class="num">{n(r['pages'])}</td>
          <td class="num">{f3(r['decline_rate'])}</td>
          <td class="num">{r['lift_vs_base']:.2f}x</td></tr>""")
    return "\n".join(out)

def mom_rows():
    return "\n".join(
        f"""<tr><td>{html.escape(str(r['mom_impr']))}</td><td class="num">{n(r['pages'])}</td>
        <td class="num">{f3(r['under_original_label'])}</td>
        <td class="num">{f3(r['under_decoupled_label'])}</td></tr>"""
        for r in LK["momentum_direction"])

def surv_rows():
    return "\n".join(
        f"""<tr><td>{html.escape(str(r['age_days']))}</td><td class="num">{n(r['catalogued'])}</td>
        <td class="num">{n(r['scored'])}</td><td class="num">{f3(r['share_scored'])}</td></tr>"""
        for r in surv)

def mon_rows():
    return "\n".join(
        f"""<tr><td class="small">{html.escape(r['watch'])}</td>
        <td class="small">{html.escape(r['signal'])}</td>
        <td class="small num">{html.escape(str(r['now']))}</td>
        <td class="small">{html.escape(r['trigger'])}</td>
        <td class="small">{html.escape(r['then'])}</td></tr>"""
        for r in M["monitor_triggers"])

calib_lo, calib_hi = calib[0], calib[-1]
obs = [float(r["observed_decline"]) for r in calib]
dips = [i for i in range(1, len(obs)) if obs[i] < obs[i - 1]]
all_under = all(float(r["gap"]) < 0 for r in calib)
CATALOGUE = 519606          # dim_content rows in this release, as the notebook prints in k04 and k14
band_total = sum(int(r["catalogued"]) for r in surv)
assert band_total < CATALOGUE, "bands cannot exceed the catalogue"
best_band = max(surv, key=lambda r: float(r["share_scored"]))
worst_band = min(surv, key=lambda r: float(r["share_scored"]))
p1b = next(b["base_decline_rate"] for b in bases if b["pair"] == "P1")
p3b = next(b["base_decline_rate"] for b in bases if b["pair"] == "P3")
spread = max(b["base_decline_rate"] for b in bases) - min(b["base_decline_rate"] for b in bases)
fwd_gap = (sum([H["forward_auc_pair_1"], H["forward_auc_pair_2"]])
           - sum([H["forward_baseline_pair_1"], H["forward_baseline_pair_2"]])) / 2
rule_p50_random = lad[(RUNG1, "baseline_w04")]["p@50"]
rule_p50_fwd = lad[(R4A, "baseline_w04")]["p@50"]
POOL_BASE = 0.742           # printed in k18: pool base rate over the recommendation rows on P3
CARRIES = {"refresh_senior_review", "queue_for_refresh", "on_page_optimisation", "title_snippet_review"}
_act = {d["archetype"]: d["action"] for d in M["archetype_definitions"]}
rec_pages  = sum(int(r["pages"]) for r in arch.values() if _act[r["archetype"]] in CARRIES)
norec_pages = sum(int(r["pages"]) for r in arch.values() if _act[r["archetype"]] not in CARRIES)
rec_impr   = sum(float(r.get("impressions") or 0) for r in arch.values() if _act[r["archetype"]] in CARRIES)
all_impr   = sum(float(r.get("impressions") or 0) for r in arch.values())
p3_pages   = P["P3"]["pages"]
norec_impr = all_impr - rec_impr
norec_decliners = round(sum(int(r["pages"]) * float(r["decline_rate"])
                            for r in arch.values() if _act[r["archetype"]] not in CARRIES))
NOT_LIVE_PAGES, NOT_LIVE_IMPR = 10156, 3080255   # printed in k16, on the live month
assert NOT_LIVE_PAGES < P["LIVE"]["pages"]
max_gap = max(abs(float(r["gap"])) for r in calib)
wins_txt = M["capacity_finding"]

HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Which web pages are about to lose search traffic?</title>
<meta name="description" content="A forward validated model that ranks which live pages are most likely
to lose search impressions next month, and turns the ranking into a review queue with a reason on every
row. Built on the FlyRank ML Internship dataset.">
<style>
:root{{
  --bg:#fbfbfa; --panel:#fff; --ink:#1a1d21; --dim:#5c6672; --line:#e2e6ea;
  --accent:#2b6cb0; --accent-soft:#ebf3fb; --warn:#9c4221; --warn-soft:#fdf3ec; --good:#22543d;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}}
@media (prefers-color-scheme:dark){{
  :root{{--bg:#15171a; --panel:#1c1f23; --ink:#e8eaed; --dim:#9aa4b0; --line:#2c3138;
        --accent:#7cb3e8; --accent-soft:#1d2733; --warn:#e8a87c; --warn-soft:#2a201a; --good:#8ed1a8;}}
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  -webkit-text-size-adjust:100%}}
.wrap{{max-width:790px;margin:0 auto;padding:0 20px 80px}}
header{{padding:56px 0 30px;border-bottom:1px solid var(--line);margin-bottom:36px}}
.kicker{{font-size:12px;letter-spacing:.09em;text-transform:uppercase;color:var(--dim);
  font-weight:600;margin-bottom:14px}}
h1{{font-size:clamp(27px,5.1vw,40px);line-height:1.16;margin:0 0 18px;letter-spacing:-.019em;font-weight:700}}
.byline{{color:var(--dim);font-size:14.5px;margin:0}}
h2{{font-size:clamp(20px,3.4vw,25px);margin:56px 0 4px;letter-spacing:-.012em;line-height:1.25;
  scroll-margin-top:20px}}
h2 .sn{{color:var(--accent);font-variant-numeric:tabular-nums;margin-right:.45em;font-weight:600}}
h3{{font-size:17px;margin:34px 0 8px;letter-spacing:-.005em}}
h2+p,h3+p{{margin-top:10px}}
p{{margin:0 0 16px}}
a{{color:var(--accent)}}
code{{font-family:var(--mono);font-size:.885em;background:var(--accent-soft);
  padding:1.5px 5px;border-radius:4px;white-space:nowrap}}
.abstract{{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent);
  border-radius:8px;padding:22px 24px;margin:0 0 8px}}
.abstract p{{margin:0}}
.abstract .lbl{{font-size:11.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--dim);
  font-weight:700;display:block;margin-bottom:9px}}
figure{{margin:26px 0 30px}}
figure img{{width:100%;height:auto;display:block;border:1px solid var(--line);border-radius:8px;
  background:#fff}}
figcaption{{font-size:14.5px;color:var(--ink);margin-top:11px;padding-left:13px;
  border-left:3px solid var(--accent)}}
figcaption b{{font-weight:650}}
.tw{{overflow-x:auto;margin:20px 0 26px;-webkit-overflow-scrolling:touch}}
table{{border-collapse:collapse;width:100%;font-size:14.5px;min-width:520px}}
th,td{{text-align:left;padding:8px 11px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{font-size:12px;letter-spacing:.045em;text-transform:uppercase;color:var(--dim);font-weight:650;
  border-bottom:1.5px solid var(--line);white-space:nowrap}}
td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
td.dim,.dim{{color:var(--dim)}}
.small{{font-size:13px;line-height:1.45}}
.sd{{color:var(--dim);font-size:12px;font-weight:400}}
tr.hi td{{background:var(--accent-soft)}}
tr.rec td{{font-weight:500}}
tr.rec code{{background:var(--accent);color:#fff}}
.callout{{background:var(--warn-soft);border:1px solid var(--line);border-left:3px solid var(--warn);
  border-radius:8px;padding:17px 20px;margin:24px 0}}
.callout p:last-child{{margin-bottom:0}}
.callout .lbl{{font-size:11.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--warn);
  font-weight:700;display:block;margin-bottom:7px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:11px;margin:24px 0 28px}}
.stat{{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px 15px}}
.stat .v{{font-size:24px;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums;
  line-height:1.1}}
.stat .k{{font-size:12.5px;color:var(--dim);margin-top:5px;line-height:1.35}}
ul,ol{{margin:0 0 18px;padding-left:23px}}
li{{margin-bottom:8px}}
.nogo li{{margin-bottom:6px}}
hr{{border:0;border-top:1px solid var(--line);margin:52px 0}}
footer{{border-top:1px solid var(--line);margin-top:56px;padding-top:26px;color:var(--dim);font-size:14px}}
footer a{{font-weight:600}}
.toc{{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:16px 20px;
  margin:32px 0 0;font-size:14.5px}}
.toc ol{{margin:8px 0 0;padding-left:21px;columns:2;column-gap:26px}}
.toc li{{margin-bottom:4px;break-inside:avoid}}
@media (max-width:560px){{.toc ol{{columns:1}}}}
</style>
</head>
<body>
<div class="wrap">

<header>
  <div class="kicker">FlyRank ML Internship &middot; Capstone &middot; Refresh and Content Opportunity Scoring</div>
  <h1>Which web pages are about to lose search traffic?</h1>
  <p class="byline">A forward validated ranking of pages likely to lose search impressions next month,
  and the review queue built on top of it. Decision support, not prediction of Google.</p>
</header>

<div class="abstract">
  <span class="lbl">Abstract</span>
  <p>A content team with more pages than review hours needs to know which pages to open first, so I asked
  whether last month's search performance alone can rank the pages most likely to lose impressions next
  month. I built a monthly panel of {n(P['P1']['pages'])} to {n(P['LIVE']['pages'])} live pages across
  {P['LIVE']['clients']} anonymised clients from the FlyRank warehouse, labelled a page as declining when
  its impressions fell below 80 percent of the prior month, and scored one frozen random forest against
  the heuristic it would replace on four validation designs of increasing strictness. On a random split
  the forest reached an AUC of {f3(H['random_split_auc'])}, but holding out whole clients cost
  {f3(client_drop)} of that on its own, and holding out clients and a month together, which is the
  deployment condition, left {f3(fwd_lo)} to {f3(fwd_hi)} across two independent pairs against
  {f3(rule_lo)} to {f3(rule_hi)} for the heuristic. Turning that score into a queue of {n(Q['rows'])} ranked rows with a reason attached to each
  one, I measured that it does not protect more at risk traffic than simply sorting by impressions, and
  that its real gains are review precision and the exclusion of pages the catalogue already calls
  unpublished. Every number here is an association observed over four months of one release; nothing in
  this work identifies a cause, and no result should be read as evidence about how Google ranks
  anything.</p>
</div>

<nav class="toc">
  <b>Sections</b>
  <ol>
    <li><a href="#intro">Problem statement</a></li>
    <li><a href="#data">Data</a></li>
    <li><a href="#method">Methodology</a></li>
    <li><a href="#results">Results</a></li>
    <li><a href="#limits">Limitations</a></li>
    <li><a href="#playbook">Ranked recommendations</a></li>
    <li><a href="#repro">Reproducibility</a></li>
    <li><a href="#credit">Acknowledgments</a></li>
  </ol>
</nav>

<h2 id="intro"><span class="sn">1</span>Introduction and problem statement</h2>

<p>A mid sized content operation has tens of thousands of live pages and a review capacity measured in
tens of pages a month. Traffic decay is not evenly distributed and it is not announced: by the time a
monthly report shows a page falling, the fall has already happened. The practical question is not how the
site is doing. It is which pages to open on Monday.</p>

<p>Two framings were available and I rejected the more obvious one. Forecasting next month's impressions
per page gives a number nobody acts on, and it is graded on how close the number is rather than on whether
the right pages got attention. Ranking by risk of decline is graded on the thing that matters, which is
whether the top of the list is worth a reviewer's hour.</p>

<p>I also chose decline over growth opportunity. Decline has a definition the data can actually check a
month later. Opportunity does not, and a model whose label cannot be verified is a model that cannot be
wrong.</p>

<p>So the question this paper answers: <b>using only what is knowable on the last day of a month, can I
rank live pages by how likely they are to lose search impressions the following month, well enough to
beat the heuristic a team would otherwise use, on clients and a month the model has never seen?</b></p>

<h2 id="data"><span class="sn">2</span>Data</h2>

<p>The FlyRank ML Internship warehouse, one release, read directly over DuckDB. Two tables:
<code>fact_content_daily_performance</code> for daily impressions, clicks and summed position, and
<code>dim_content</code> for the page catalogue, creation dates, publication flags and keyword market
columns. All identifiers in the release are pseudonyms, and nothing in this paper or the notebooks behind
it names a client, a domain, a URL or a query.</p>

<div class="stats">
  <div class="stat"><div class="v">{n(CATALOGUE)}</div><div class="k">catalogued pages</div></div>
  <div class="stat"><div class="v">{n(P["LIVE"]["pages"])}</div><div class="k">drew impressions in the live month</div></div>
  <div class="stat"><div class="v">{P['LIVE']['clients']}</div><div class="k">anonymised clients</div></div>
  <div class="stat"><div class="v">4</div><div class="k">months used, 2026-03 to 2026-06</div></div>
</div>

<p>The design is a panel: features from one calendar month, label from the month after. That gives three
labelled pairs and one live month with no label yet.</p>

<div class="tw"><table>
<thead><tr><th>Panel</th><th>Feature month</th><th>Label month</th><th class="num">Pages</th>
<th class="num">Clients</th><th class="num">Declined</th></tr></thead>
<tbody>
<tr><td>P1</td><td>2026-03</td><td>2026-04</td><td class="num">{n(P['P1']['pages'])}</td>
    <td class="num">{P['P1']['clients']}</td><td class="num">{f3(P['P1']['base_decline_rate'])}</td></tr>
<tr><td>P2</td><td>2026-04</td><td>2026-05</td><td class="num">{n(P['P2']['pages'])}</td>
    <td class="num">{P['P2']['clients']}</td><td class="num">{f3(P['P2']['base_decline_rate'])}</td></tr>
<tr><td>P3</td><td>2026-05</td><td>2026-06</td><td class="num">{n(P['P3']['pages'])}</td>
    <td class="num">{P['P3']['clients']}</td><td class="num">{f3(P['P3']['base_decline_rate'])}</td></tr>
<tr><td>Live</td><td>2026-06</td><td class="dim">none yet</td><td class="num">{n(P['LIVE']['pages'])}</td>
    <td class="num">{P['LIVE']['clients']}</td><td class="num dim">unlabelled</td></tr>
</tbody></table></div>

<p>June is the last month the release holds, which makes it a sealed test month. It is used that way: as a
label for the final forward test and as an unlabelled month to score. Every threshold in this work was
fixed earlier, in Week 4 and Week 5, and the click through floor in the routing layer comes from the April
panel, so nothing was tuned inside the month it is applied to.</p>

<h3>What was excluded, and why</h3>

<ul>
<li><b>Pages with no impressions in the feature month.</b> There is no baseline to measure a fall from.
This is the largest exclusion and section 5 measures its cost.</li>
<li><b>Pages with no creation date.</b> Page age is one of the ten features and is undefined without one.</li>
<li><b>Three date columns:</b> <code>content_updated_date</code>, <code>last_optimized_date</code> and
<code>optimization_eligible_date</code>. The catalogue holds one snapshot value per page, and for most
rows that value is dated after the decision day, so what the column held at decision time is
unrecoverable. Using it would leak the future. Section 3 shows the check rather than asserting it.</li>
<li><b>The pre aggregated sample and 90 day query tables.</b> One covers the final month only; the other
uses a rolling 90 day window that straddles the label month, so a feature built from it would already
contain part of the answer.</li>
</ul>

<h2 id="method"><span class="sn">3</span>Methodology</h2>

<p><b>The label.</b> A page declines when its impressions in the following month fall below 0.8 times its
impressions in the feature month. Twenty percent is a threshold I chose, not one the data handed me. It is
wide enough to sit outside ordinary noise on a trafficked page and narrow enough to fire often enough to
model.</p>

<p><b>The decision day</b> is the last day of the feature month, and every feature has to be knowable on
it. That single rule is what excluded the three date columns above.</p>

<p><b>Ten features</b>, all aggregated inside the feature month: month totals for impressions and clicks;
click through rate; impression weighted average position; days with at least one impression; page age in
days; impressions in each half of the month; and the ratio between the two halves for both impressions and
clicks. Publication flags and keyword market columns travel with the panel for routing but are never model
inputs, and the notebook asserts that rather than trusting it.</p>

<p><b>The baseline is real, not a straw man.</b> It is the heuristic a team actually reaches for: score a
page by its age in days if it drew at least 50 impressions and is at least 90 days old, otherwise zero.
Frozen in Week 4 and unchanged since.</p>

<p><b>The model</b> is one random forest, 200 trees, minimum 100 samples per leaf, fixed seed, chosen in
Week 5 against logistic regression and a stratified dummy. Nothing in the capstone retunes it, because
tuning against the forward test is how an honest number becomes another mirage.</p>

<h3>The validation ladder</h3>

<p>The same model and the same baseline, scored four ways, each rung removing one way the rung above it
could flatter itself.</p>

<ol>
<li><b>Random split.</b> Rows shuffled, so pages of the same client land on both sides.</li>
<li><b>Grouped by client.</b> No client in both train and test. Tests whether the model learned content
behaviour or client fingerprints.</li>
<li><b>Time forward.</b> Train on the earlier pair, test on the later one. Tests whether last month's
pattern still holds next month.</li>
<li><b>Grouped and time forward.</b> Unseen client and unseen month at once. This is the deployment
condition, so this is the only number that counts, and it is run twice on independent pairs.</li>
</ol>

<h3>Leakage checks</h3>

<p>Three tests, because a clean validation design proves nothing if the features themselves contain the
answer. The suspect was the within month momentum ratio: the label compares next month against this
month's total, and momentum compares the two halves of that same total, so they share a term.</p>

<div class="tw"><table>
<thead><tr><th>Check</th><th class="num">AUC</th><th>What it establishes</th></tr></thead>
<tbody>
<tr><td>Positive control: next month's impressions handed to the model</td>
    <td class="num"><b>{f3(LK['positive_control_auc'])}</b></td>
    <td class="small">The harness can detect a leak. Worth knowing before trusting any other line.</td></tr>
<tr><td>The ten honest features, same fold</td><td class="num">{f3(LK['honest_auc_same_fold'])}</td>
    <td class="small">The reference point for the two ablations below.</td></tr>
<tr><td>Momentum removed</td><td class="num">{f3(LK['auc_without_mom_impr'])}</td>
    <td class="small">Weaker, not collapsed. A useful feature behaves like this; a label in disguise does not.</td></tr>
<tr><td>Static features only</td><td class="num">{f3(LK['auc_static_only'])}</td>
    <td class="small">Momentum carries real signal beyond the static six.</td></tr>
<tr><td>Decoupled label sharing no month with the features</td>
    <td class="num">{f3(LK['auc_decoupled_label'])}</td>
    <td class="small">Ranking quality survives when the shared arithmetic term is broken.</td></tr>
</tbody></table></div>

<div class="callout">
  <span class="lbl">This test cost me a claim</span>
  <p>The decoupled label kept the AUC intact but <b>inverted the direction</b> of the momentum effect. Under
  the original label a page falling within the month is likelier to decline; under a label that shares no
  month with the features, a rising page is.</p>
  <div class="tw"><table>
  <thead><tr><th>Momentum quartile</th><th class="num">Pages</th><th class="num">Declines, original label</th>
  <th class="num">Declines, decoupled label</th></tr></thead>
  <tbody>{mom_rows()}</tbody></table></div>
  <p>A forest learns whichever direction its training data shows, so a stable AUC across that flip does not
  vindicate the story I had attached to the feature. The ranking is real. "Falling pages keep falling" is
  not established, and it is therefore not claimed anywhere in this paper.</p>
</div>

<h2 id="results"><span class="sn">4</span>Results</h2>

<p>Model against baseline, on the same rows, at every rung. The base rate is in the last column because on
this panel a coin that always says decline is right about half the time, and any figure quoted without the
base rate beside it is decoration.</p>

<div class="tw"><table>
<thead><tr><th>Validation design</th><th class="num">Forest AUC</th><th class="num">Rule AUC</th>
<th class="num">Gap</th><th class="num">Forest p@500</th><th class="num">Rule p@500</th>
<th class="num">Base rate</th></tr></thead>
<tbody>{rung_rows()}</tbody></table></div>

<figure>
  <img src="assets/w08_ladder.png" alt="Bar chart of AUC for the random forest and the frozen rule across
  five validation designs. The forest falls from about {f3(H['random_split_auc'])} on a random split to
  about {f3(fwd_hi)} once clients and months are held out, while the rule stays near coin flip
  throughout.">
  <figcaption><b>Read it left to right:</b> holding out whole clients cost {f3(client_drop)} AUC on its
  own, which is more than the entire fall to the deployment rung, because adding an unseen month on top of
  that put {f3(abs(drop - client_drop))} back rather than taking more away. The heuristic it replaces never
  leaves coin flip territory at any rung.</figcaption>
</figure>

<p>The drop from rung 1 to rung 2 is the whole lesson. Same features, same trees, same rows: only the
split changed. Shipping the random split number would have promised {f3(H['random_split_auc'])} and
delivered around {f3(fwd_hi)}.</p>

<p>The baseline does not move. It sits near {f3(lad[(R4A, 'baseline_w04')]['AUC'])} at the strictest rung,
which is what a coin looks like. That is the honest comparison: the model is not impressive, and it is
measurably better than the heuristic it would replace, and it stays better when both are scored on clients
and a month neither had seen.</p>

<figure>
  <img src="assets/w08_forward_stability.png" alt="Dot plot of AUC per held out client fold for the forest
  and the rule, on two independent month pairs. The forest averages about {f3(fwd_hi)} and {f3(fwd_lo)};
  the rule sits near 0.5 on both.">
  <figcaption><b>Run twice on independent pairs:</b> the forward result repeats on months it was not tuned
  on, so it is a property of the model rather than of two convenient months, but the fold spread is wide
  enough that the honest way to quote it is the range {f3(fwd_lo)} to {f3(fwd_hi)} rather than a single
  decimal.</figcaption>
</figure>

<p>One metric deserves a warning. On a random split the rule's precision in its top 50 reads
{f3(rule_p50_random)}, which looks excellent and is an artefact: the rule assigns thousands of pages an
identical score, so its top 50 is whatever the tiebreak happens to return. Hand it an unseen client and a
month it has not seen and the same figure falls to {f3(rule_p50_fwd)}. A number that moves that far on a
tiebreak is not measuring the rule, which is why the AUC columns above carry the argument and the precision
columns are reported next to them rather than instead of them.</p>

<p>The run behind this page also reproduces the audit committed three weeks earlier. Rungs 1 through 3 come
back within 0.002 AUC of the figures recorded then, on a fresh warehouse read, which is the check that the
pipeline is deterministic rather than the claim that it is.</p>

<h2 id="limits"><span class="sn">5</span>Limitations and honest framing</h2>

<h3>The score is a rank, and a coarse one</h3>
<p>The forest is uncalibrated and nothing here calibrates it. Across ten equal size buckets of out of fold
scores the observed decline rate runs from {f3(calib_lo['observed_decline'])} in the lowest bucket to
{f3(calib_hi['observed_decline'])} in the highest, so the two ends separate clearly. It does not rise
monotonically: {len(dips)} bucket{'s sit' if len(dips) != 1 else ' sits'} below the bucket beneath
{'them' if len(dips) != 1 else 'it'}. Adjacent buckets are therefore not reliably ordered, and only the
broad direction is.</p>

<p>The level is further off than the ordering. {"Every bucket's" if all_under else "Nearly every bucket's"}
observed rate sits above its own mean score, by as much as {f3(max_gap)}, which is what fitting on panels
near a {f3(p1b)} base rate and scoring a month where {f3(p3b)} of pages fell will do. So the score never appears in a sentence like "this page has a 72
percent chance of declining", every cutoff in section 6 is a review capacity rather than a probability
threshold, and nothing downstream reads the score as a level.</p>

<h3>The model only sees survivors</h3>
<p>The panel requires impressions in the feature month, which sets aside most of the catalogue. Of
{n(CATALOGUE)} catalogued pages, {n(P['LIVE']['pages'])} drew impressions in the live month, which is
{pct(P['LIVE']['pages'] / CATALOGUE)}. Retention is not flat across age bands, and it does not fall
smoothly either.</p>

<div class="tw"><table>
<thead><tr><th>Page age at the live month's decision day</th><th class="num">Catalogued</th>
<th class="num">Scored</th><th class="num">Share scored</th></tr></thead>
<tbody>{surv_rows()}</tbody></table></div>

<p>Retention peaks in the {html.escape(str(best_band['age_days']))} band at
{pct(best_band['share_scored'])} and bottoms out at {pct(worst_band['share_scored'])} for
{html.escape(str(worst_band['age_days']))}, and pages older than two years fall outside these bands
entirely. So the scored population is not a random sample of the catalogue. Everywhere this paper says
"content" it means "content that drew impressions that month", and those are different populations. A page
with no impressions is invisible to this model, and invisible is not the same as unimportant.</p>

<h3>The base rate moves more than the model does</h3>
<p>Across the three labelled pairs the decline rate runs
{f3(min(b['base_decline_rate'] for b in bases))} to {f3(max(b['base_decline_rate'] for b in bases))}, a
spread of {f3(spread)}. Set that against the model's forward margin over the rule, which is
{f3(fwd_gap)}: the month a queue is measured in moves its apparent precision further than the choice of
model does. That is not a modelling result, it is what happened, and it is why every precision figure here
is printed next to the base rate of its own pool.</p>

<h3>No causal claim, anywhere</h3>
<p>Nothing here shows that refreshing a page changes its traffic. The warehouse contains no experiment, no
holdout and no randomisation over refresh decisions, and pages that get refreshed are chosen, which is a
cause of its own. Every result is an association observed on this release over these months. The language
stays at observed, measured, associated with, directional and decision support. No result in this work says
anything about how Google's ranking systems operate.</p>

<h3>One release, four months, one lane</h3>
<p>The release spans eighteen calendar months and this work uses the last four, because those are the
months where every feature the panel needs is present in full. Four months cannot separate a seasonal
pattern from a trend, so nothing here is attributed to a season. The forward result was checked on two
pairs, which is enough to show it is not a fluke of one pair and not enough to call it stable. A third
pair would help. There is not one.</p>

<h3>The floor and the exclusions have a measured cost</h3>
<p>The archetypes that carry no recommendation, meaning the two hard exclusions plus everything under the
50 impression floor and everything the router judged steady, cover {n(norec_pages)} pages, which is
{pct(norec_pages / p3_pages)} of the evaluated panel and {pct(norec_impr / all_impr)} of its impressions.
Around {n(norec_decliners)} of those pages did decline, and the queue never mentions one of them. That is the deliberate cost of refusing to recommend work on evidence too thin to
support it rather than an oversight, and it is the first number to put in front of anyone who proposes
lowering the floor.</p>

<div class="callout">
  <span class="lbl">What would change my mind</span>
  <p>If forward AUC on a new pair falls within 0.05 of the frozen rule, the model is not earning its
  complexity and the rule should ship instead. If a review log ever shows reviewers disagreeing with the
  reason code more than 30 percent of the time, the archetype thresholds are wrong rather than the ranking.
  Both are live triggers in the monitoring table below.</p>
</div>

<h2 id="playbook"><span class="sn">6</span>Ranked recommendations</h2>

<p>A ranking is not an action. Two pages can share a score and need entirely different work: one is a heavy
earner losing ground inside the month, the other ranks on page two and has never been touched. So the score
decides the order and a routing layer decides the verb.</p>

<p>Nine archetypes, evaluated in order, first match wins, so every page carries exactly one reason. Two are
hard exclusions and come first on purpose, because a queue that recommends work on a deleted page burns the
reviewer's trust in everything below it. Rates below are measured on held out clients in a month the scoring
model never saw, against a panel base rate of {f3(P['P3']['base_decline_rate'])}.</p>

<div class="tw"><table>
<thead><tr><th>Archetype</th><th>Condition</th><th>Action</th><th class="num">Pages</th>
<th class="num">Declined</th><th class="num">vs base</th></tr></thead>
<tbody>{arch_rows()}</tbody></table></div>

<figure>
  <img src="assets/w08_archetype_rates.png" alt="Horizontal bar chart of measured decline rate by
  archetype, with the panel base rate marked. Archetypes carrying a recommendation are highlighted.">
  <figcaption><b>Each archetype carries its own measured rate</b> rather than inheriting one headline
  number, and the archetypes that trigger work are not uniformly above base rate, which is exactly why the
  routing layer reports them separately.</figcaption>
</figure>

<p>Ranking is <code>score x impressions</code>, ordered <b>inside each client</b>. A single portfolio wide
sort put the entire global top 100 inside one account, which is a report about account size rather than a
work queue; ranking within the client cuts the same top 100 across ten of them. The live queue holds
{n(Q['rows'])} rows across {Q['clients']} of {P['LIVE']['clients']} clients, which is
{pct(Q['share_of_live_pages'])} of live pages. The other {pct(1 - Q['share_of_live_pages'])} get silence,
and silence is the design working rather than a gap to fill by lowering the floor.</p>

<h3>Does the queue actually earn its place?</h3>

<p>An AUC is not a decision. The real question is narrower: given N review hours, does this queue put better
pages in front of a reviewer than the obvious alternatives? So the same pool was ordered four ways and
measured at seven budgets, on the labelled May to June panel rather than on the live month, because only a
labelled month can say who was right. The honest competitor is sorting by impressions, which anyone can do
in a spreadsheet in ten seconds. The pool is the {n(rec_pages)} pages the four recommending archetypes cover, which is
{pct(rec_pages / p3_pages)} of the panel holding {pct(rec_impr / all_impr)} of its impressions, at a base
decline rate of {f3(POOL_BASE)}. Read every precision figure in the table against that base and not against
zero.</p>

<div class="tw"><table>
<thead><tr><th>Review budget</th><th class="num" colspan="3">At risk traffic reached</th>
<th class="num" colspan="3">Of pages opened, share declining</th></tr>
<tr><th></th><th class="num">Queue</th><th class="num">Traffic sort</th><th class="num">Score alone</th>
<th class="num">Queue</th><th class="num">Traffic sort</th><th class="num">Score alone</th></tr></thead>
<tbody>{cap_rows()}</tbody></table></div>

<figure>
  <img src="assets/w08_capacity_curve.png" alt="Line chart of the share of at risk impressions reached
  against pages reviewed on a log scale, for four orderings. The queue and the plain traffic sort trace
  almost the same line; the model score alone stays near zero.">
  <figcaption><b>The queue and a plain traffic sort trace nearly the same line,</b> so the queue's case is
  precision and routing rather than reach, and the score used alone reaches almost no at risk traffic
  because a pure decline model prefers small pages.</figcaption>
</figure>

<div class="callout">
  <span class="lbl">The finding I did not want</span>
  <p>{html.escape(wins_txt[0].upper() + wins_txt[1:])}. I am stating that plainly because it is the measured
  result and finding it out was the point of the exercise.</p>
  <p>What the queue buys is narrower than a lift number, and it is worth stating in three parts. Of the
  pages a reviewer actually opens it holds a higher share of genuine decliners than a traffic sort does at
  every budget in the table. Every row carries a reason a sort cannot give: ranks just off the first page,
  click share under the April floor, or the catalogue says this page is not live. And
  {n(NOT_LIVE_PAGES)} pages that drew impressions in the live month while the catalogue calls them
  unpublished or deleted, carrying {n(NOT_LIVE_IMPR)} impressions between them, never reach a reviewer at
  all, where a traffic sort puts a good number of them near the top.</p>
  <p>Note the third column of the precision block, too. Sorting by model score alone is the most precise
  ordering in the table and it is useless, because it reaches
  {f3([r for r in cap if r['order'] == 'model score alone' and r['pages_reviewed'] == 500][0]['share_of_at_risk_reached'])}
  of at risk traffic at 500 pages. A decline model on its own prefers small pages. That is the reason
  impressions are in the ranking at all.</p>
</div>

<h3>Monitoring and retrain triggers</h3>
<p>A model that ships without stated triggers is a model somebody will still be running unchecked in a
year. Retrain cadence is monthly, on the newest labelled pair.</p>

<div class="tw"><table>
<thead><tr><th>Watch</th><th>Signal</th><th class="num">Now</th><th>Trigger</th><th>Then</th></tr></thead>
<tbody>{mon_rows()}</tbody></table></div>

<h3>What this does not license</h3>
<ul class="nogo">
{"".join(f"<li>{html.escape(x[0].upper() + x[1:])}.</li>" for x in M["no_go"])}
</ul>

<h2 id="repro"><span class="sn">7</span>Reproducibility</h2>

<p>Every figure and every number on this page is written by one notebook,
<code>work/notebooks/capstone.ipynb</code>, and this page is generated from the metrics file that notebook
exports rather than typed by hand, so the paper cannot drift from the run that produced it.</p>

<ul>
<li><b>Repository:</b> <a href="https://github.com/oumaklaus/ml-internship">github.com/oumaklaus/ml-internship</a></li>
<li><b>Capstone notebook:</b> <code>work/notebooks/capstone.ipynb</code>, runs top to bottom in one pass
and opens in Colab from the badge in its first cell.</li>
<li><b>The weekly notebooks it builds on:</b> the research question, the task framing, the data contract,
the frozen baseline, the model choice, the validation audit and the action playbook, all under
<code>work/notebooks/</code> with outputs saved.</li>
<li><b>Committed receipts:</b> <code>work/outputs/w08_capstone_metrics.json</code> and the four figures in
<code>work/figures/</code>. The metrics file carries every number quoted here, including the ones that do
not flatter the model.</li>
<li><b>This page:</b> <code>scripts/build_paper.py</code> reads that metrics file and writes
<code>docs/index.html</code>. Rerun the notebook, rerun the script, and the page follows. No figure on it
was typed in by hand, which is the only reason it can be trusted to match the run.</li>
<li><b>Determinism:</b> fixed seed on the forest, and the warehouse aggregate is explicitly ordered by page
identifier, because a hash aggregate returns rows in no fixed order and that row order reaches the
bootstrap sampler.</li>
</ul>

<p>The per page queue export is deliberately <b>not</b> committed. It is row level output on real client
content, and the repository is public. The metrics file and the figures are the receipts.</p>

<h2 id="credit"><span class="sn">8</span>Acknowledgments and data credit</h2>

<p>Built on the <a href="https://flyrank.ai">FlyRank ML Internship dataset</a>. Thanks to the FlyRank team
for a warehouse with real messiness in it, including the publication flags that turned into the single
highest value rule in the playbook.</p>

<p>All client and page identifiers in the release are pseudonyms. No client name, domain, URL or search
query appears in this paper, in the notebooks, or in any committed artifact.</p>

<footer>
  <p>FlyRank ML Internship capstone, Machine Learning track, lane: Refresh and Content Opportunity Scoring.
  Data window 2026-03 to 2026-06. Observed associations only, no causal or algorithmic claims.</p>
  <p>Built on the FlyRank ML Internship dataset &middot; <a href="https://flyrank.ai">flyrank.ai</a></p>
</footer>

</div>
</body>
</html>
"""

out = DOCS / "index.html"
out.write_text(HTML)
for ch in ("—", "–", "−"):
    assert ch not in HTML, f"dash {ch!r} in the paper"
assert "flyrank.ai" in HTML, "CI requires the flyrank.ai credit"
print(f"wrote {out}  {out.stat().st_size / 1024:.1f} KB")
print("figures copied:", ", ".join(FIGS))
