I'll review this research paper as a read-only quant PM reviewer. Let me start by exploring the repository structure and reading the key files.

Let me read the main report and key docs in parallel.

The route_b doc is well-disciplined. Now let me read the main report in sections and the other key docs.

The report is well-structured. Let me read the remaining sections in parallel.

Now the Results, Discussion, and Conclusion sections.

Now the Discussion and Conclusion sections.

The report is impressively disciplined. Now let me read the supporting audit docs and verify claims against artifacts.

Let me read the improvement plan and reviewer doc, and inspect the artifacts directory.

Let me verify the key numbers against the actual artifacts.

Now let me verify the headline statistics against the actual artifact CSVs.

The artifacts match the report claims precisely. Let me verify the figures, page count, and the frequency-diagnostic numbers.

All figures present and the PDF is freshly compiled. Let me confirm the page count (the improvement plan flagged a >10-page issue) and check the log.

PDF is 10 pages (within limit) and freshly compiled; frequency-diagnostic numbers match. One thing stands out: in `momentum_daily_ic_robustness.csv`, the Newey–West t-stat *increases* monotonically with lag (plain 3.54 → NW-lag21 4.39 → NW-lag63 5.23), which is the opposite of the usual HAC behavior for a persistent series. Let me inspect the script computing this.

The Newey–West implementation is textbook-correct (Bartlett kernel); the t-stat rising with lag reflects genuine *negative* autocorrelation in the daily IC series, not a bug — though it will surprise reviewers. Let me do a final consistency check on the leakage and survivorship support docs.

I've completed a full read-only review: read the entire `sp500_case_study.tex`, the Route B / P0 audit / triage / improvement-plan / reviewer docs, and verified every headline statistic against the artifact CSVs. All reproduce exactly. Here is my assessment as the Copilot Opus paper reviewer.

---

## Reviewer status
The Copilot Opus reviewer gate ran (this read-only pass). Outcome: **no P0 paper-level blockers.** The report is methodologically sound, the numbers reproduce from `report/artifacts/`, and failed methods are honestly demoted. Findings below are P1/P2 quality-and-credibility issues plus residual risks.

## Verification performed (all pass)
- Paired increment `t=0.25`, corr `0.93`, +0.5% ann, Sharpe-gap CI `[-0.17,0.63]` ✓ (`route_b_paired_increment`)
- Momentum 30d Sharpe `0.740`, mean-ret `t=1.51`, boot CI `[-0.22,1.85]` ✓ (`route_b_momentum_baseline`)
- Daily IC `t=3.54`, NW21 `4.39`, block CI `[0.0115,0.0297]` ✓; traded-horizon block-boot `t=2.41/2.13/1.89/1.85`, 20d/30d CIs cross zero ✓
- PIT inclusion `0.741→0.446` mom, `0.987→0.725` overlay ✓; canonical RankIC `0.0279` vs `0.0282` ✓; DSR full-grid `0.003`, PBO `50%`, sleeve DSR `0.055` ✓
- 10 pages, freshly compiled; all 6 figures present; Newey–West code is textbook-correct (Bartlett kernel).

---

## Blocker findings (none P0)

**P1 — The endorsed headline pairs a Sharpe number with a claim it never significance-tests.** §1 / §Conclusion / Table `tab:results` (lines 70–73, 817, 983–987) call the 5-day momentum book "the strongest tradable row (net Sharpe 0.63…)". But only the *30d* book has a reported Sharpe CI. Over ~222 non-overlapping 5-day periods, Sharpe 0.63 implies a mean-return t ≈ 0.63·√(222/50.4) ≈ **1.3 — i.e. likely *not* statistically significant as a portfolio.** So *no* momentum book (5/20/30d) is shown to have a significant net Sharpe; significance lives only in the IC (5d block-boot t=2.41, and strongest at the *non-tradable* 1-day horizon). Impact: the paper's single endorsed tradable signal is asserted on a Sharpe whose own error bar is unreported and probably crosses the insignificance line. Fix: report bootstrap Sharpe CI + mean-return t for the 5d (and 20d) books, and explicitly anchor the endorsement on **IC significance + turnover**, not the Sharpe point estimate.

**P1 — "Strongest tradable" conflicts with the table.** Table `tab:results`: 5d Sharpe **0.63** < 20d **0.82** < 30d 0.74. Calling the *lowest-Sharpe* row "strongest" without a one-line basis reads like reverse cherry-picking. Impact: a PM will ask "why not trade 20d at 0.82?" Fix: state plainly that 5d is selected because it is the only traded horizon with a strictly-positive IC bootstrap interval *and* the lowest turnover (0.22), while 20d/30d have higher Sharpe point estimates but IC CIs that cross zero.

**P2 — Newey–West t rises with lag (3.54→4.39→5.23) with no explanation.** `momentum_ic_robustness` + §1. The code is correct; the increase reflects genuine *negative* autocorrelation in the daily IC series. But unexplained, this looks like a HAC sign bug to any referee and undercuts the strongest momentum-confirmation anchor. Fix: one sentence ("daily IC is mildly negatively autocorrelated, so HAC tightens rather than widens the SE").

**P2 — DSR's "884 trials" basis is undefined.** §Results/§Discussion (lines 596, 857). DSR=0.003 is a headline-driving number and the expected-max null (1.512) scales with trial count; the older audit cites 828. Fix: one sentence defining what counts as a trial in the 884 universe.

**P2 — 30d "val-selected" model silently flips MLP→XGBoost.** Table `tab:results` lists "30d MLP (val-selected)"; Route B (§Results, Table `tab:route_b_30d`) builds the overlay on XGBoost. Fix: clarify these are the broad-search selection vs the narrower residual-label rerun.

**P2 — Non-val-selected LightGBM 30d (Sharpe 1.23, Ann 13%) is the highest number in Table `tab:results`.** Honestly flagged, but visually it reads as a buried headline. Fix: gray it / add its bootstrap CI to show it is not statistically separable from the overlay.

---

## Highest-ROI experiments (hours, current data only)
1. **Bootstrap Sharpe CI + mean-return t for the 5d and 20d momentum books** (reuse `eval_momentum_baseline.py` + the bootstrap in `build_momentum_ic_robustness.py`). Directly closes the P1 gap — either strengthens or honestly qualifies the endorsed signal.
2. **Equity-curve figure: momentum vs Route B overlay, 2022–2026.** The "main research lead" has no figure; the drawdown reduction (−13.8%→−7.3%) *is* its only selling point and should be shown.
3. **Paired-increment histogram** (overlay−momentum per period, n=35) to visualize the t=0.25 / zero-centered result.
4. Optional: a single deletion-side survivorship break-even ("delisters would need X to erase the 5d edge"), parametric, to convert the caveat into a number.

## Wording / table / figure changes for the final report
- Reframe "strongest/cleanest tradable row" → "most statistically reliable tradable benchmark (significant 5d IC + lowest turnover)"; note 20d/30d Sharpe are higher but IC-insignificant.
- Add 5d/20d Sharpe CIs (or a footnote) so every endorsed Sharpe carries error bars.
- Add the NW-vs-plain explanatory sentence and the 884-trial definition.
- Disambiguate the 30d MLP-vs-XGBoost "val-selected" labels.
- Add an overlay-vs-momentum equity-curve figure.

## Residual risks (with no P0 blocker, these are the honest weaknesses)
- **R1 Survivorship:** only the *inclusion* side is partially handled (`date_added`); the *deletion/delisting* side is unquantifiable on this current-membership dataset and is acknowledged. The 0.741→0.446 haircut is the number a PM should carry, and it is appropriately foregrounded.
- **R2 Significance lives at the wrong horizon:** the strongest evidence (1-day IC) is at a horizon you cannot trade cheaply; at tradable horizons the IC decays to insignificance by 20–30d and *no* book's Sharpe is shown significant. The paper's defensible claim is "momentum has detectable cross-sectional IC, strongest short-horizon; tradable Sharpe is positive but imprecise" — it should say this as plainly for 5d as it does for 30d.
- **R3 The one positive lead is statistically rejected** (DSR 0.003, PBO 50%, paired t=0.25, FM t=0.05). This is correctly reported, but it means the paper is, in substance, a rigorous *null* result with a risk-dampening sleeve — fine for honesty, but the conviction conclusion (trade low-turnover momentum, treat ML as a small sleeve, spend the next dollar on a PIT universe) is what carries it, so keep that POV sharp.
- **R4 Reproducibility caveat** (`docs/data_leakage_review.md`): the report-layer horizon-winner selection should be confirmed to have inherited the same `--execution-lag-days/--embargo-days/horizon` config as the training pipeline; otherwise leakage controls are asserted but not end-to-end verified for the winner path.

Net: submit-credible as an honest triage paper. Close the P1 5d-Sharpe-CI gap and the two wording issues and it reads like a senior-researcher artifact rather than a null-result writeup.

