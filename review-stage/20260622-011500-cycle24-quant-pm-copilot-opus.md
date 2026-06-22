I'll start by exploring the repository structure and reading the key files in parallel.

Let me explore the directory structure and read the core paper files.

The paper has gone through 24 review cycles. Let me read the core paper and the key referenced docs.

The paper is 1067 lines. Let me read it in sections along with the key docs.

Strong start — the paper is appropriately hedged. Let me continue reading the paper body and the audit docs.

Let me read the Results/Discussion/Conclusion sections and the remaining planning docs.

Let me read the remainder of the paper (results table, discussion, conclusion) and the improvement plan.

This is a remarkably honest, rigorous paper. Now let me verify the headline numbers against the actual artifacts and check the PDF page count, since the improvement plan flags a >10-page limit as a hard constraint.

Let me get the PDF page count via another method and verify the key Route B artifact numbers.

PDF is exactly 10 pages — the page-limit concern is resolved. Now let me cross-check the headline numbers against the artifact CSVs.

Numbers tie out precisely against artifacts. Let me check the canonical IC, paired increment, cost-breakeven, and vol-timing values that anchor the Route B claims.

Excellent — every headline number ties out to the artifacts (canonical IC 0.0279 vs 0.0282, cost gap 0.246→0.212→0.169, breakeven ~147bps, vol-timing control 0.73). Let me verify the remaining paired-increment, DSR/PBO, and capacity numbers.

All paired-increment numbers match (t=0.25, corr=0.93, gap=0.246, CI[-0.17,0.63]). Let me verify the DSR/PBO/capacity/Fama-MacBeth audit values.

Every audit number ties out exactly (DSR 0.003/0.814, PBO 50%, capacity 0.948, FM t=0.05, factor-neutral 1.006, survivorship 0.951/0.837). Let me check data/repro hygiene and read the most recent prior review to avoid repeating resolved findings.

The cycle23 review already raised the 5d-endorsement gap, "low-turnover" contradiction, and DSR framing — and the paper has since been edited (tex 01:11 > cycle23 01:01). Let me verify which of those are now resolved versus still open, so my cycle24 review is independent and non-redundant.

P2-1 (turnover contradiction) and the 1d IC split test are now resolved in the current tex. Remaining cycle23 asks (IC half-life, passive yardstick, pooled pre-2022 IC) are still absent. Let me verify the regime-slice and 5d-split numbers, then confirm the 5d Route B overlay is genuinely untested (my main new angle).

Regime slices verify exactly (5d: −0.95/0.33/−0.14/0.62, t=−1.90; 30d: −0.91/0.20/−0.12/0.67). Let me confirm the 5d residual model was already trained (making a 5d overlay cheap) while the 5d overlay backtest is genuinely absent.

Confirmed: 5d residual models are already trained, but **no 5d overlay backtest exists** — the endorsed-horizon overlay is genuinely untested. Let me check the current cycle24 placeholder and Table 4's wording before finalizing.

I have completed a full independent inspection and verified every load-bearing number against `report/artifacts/` and `output/`. I did **not** edit, commit, or run destructive commands. Here is my cycle-24 review.

---

## Reviewer gate status
Copilot Opus reviewer **ran read-only** via direct repository inspection (MCP `manual_review` not invoked in this runtime). No files edited, nothing committed, no destructive commands. Findings returned below for the orchestrator to archive into `review-stage/…cycle24…md`.

**Verification done:** PDF compiles to exactly **10 pages** (meets the limit the improvement plan flagged); all 6 figures present; PDF (01:13) is newer than tex (01:11). Every headline statistic reproduces exactly from local artifacts:
- Momentum 1d IC: discovery t=2.42 CI[0.0013,0.0119], test plain t=3.54 / NW-21 t=4.39, split ΔIC 0.0141 p=0.0049 ✔
- 5d traded split ΔIC 0.0168 CI[−0.0045,0.0380] p=0.062 ✔; regime 5d Sharpes −0.95/0.33/−0.14/0.62 (2008–11 t=−1.90) ✔
- Route B: canonical IC 0.0279 vs 0.0282; paired t=0.25, corr 0.93, gap 0.246; cost curve 0.246→0.212→0.169, breakeven ~147bps; DSR 0.003 (N=884) / 0.814 (N=14); PBO 50%; capacity 0.948/0.864; FM t=0.05; factor-neutral 1.006; survivorship 0.951/0.837; vol-timing control 0.73 ✔
- PIT 30d 0.987→0.725, momentum 0.741→0.446 ✔

**All tie out.** Repro hygiene is clean (no parquet/predictions tracked; raw data is a chunked tarball; `output/` gitignored).

## Bottom line
**No P0 paper-killing blockers.** This is a rigorous, honestly under-claiming triage paper that is clearly above a median take-home. It has improved since cycle23: the "low-turnover" contradiction is fixed (Conclusion now says momentum is kept "**not because it is cheap to trade**", line 1038), and the 1d IC discovery-vs-holdout split test was added. Remaining issues are **two substantive framing problems (P1)** and **carried-forward presentation/experiment gaps (P2)**.

---

## Blocker findings (paper-level)

### P1-A — The momentum headline is built on the *weaker* statistic; the paper buries its own strongest, most-honest evidence
**Where:** Abstract "Headline design" (lines 79–82, "The cleanest evidence is … post-2022 **minus** 2008–2021 1-day IC is 0.0141"); Table 4 read-through (line 567, "hold-out is **significantly stronger** than discovery"); Discussion/Conclusion.
**Issue:** The abstract presents *"the signal is significantly stronger post-2022"* as the **cleanest evidence for** momentum. But a regime-**improvement** statistic is ambiguous robustness evidence — "only really shows up in the recent regime" is exactly what overfitting-to-regime looks like, so leading with it *undercuts* conviction. Meanwhile the artifact `momentum_ic_robustness/` contains the genuinely strong result the paper does **not** headline: the 1-day IC is **positive and significant in BOTH sub-periods** — discovery 2008–2021 t=2.42, CI[0.0013,0.0119], p=0.0066 **and** hold-out 2022–2026 t=4.39, CI[0.0115,0.0297]. That cross-regime consistency is the convincing signal-existence proof; the recent-regime *delta* is the weaker, more-suspicious framing.
**Impact on the claim:** The paper makes its benchmark look more regime-dependent (and more like luck) than its own data shows, while spending the headline on the statistic a skeptical PM will attack.
**Fix:** Reframe the momentum evidence cleanly: **(1)** signal *existence* is cross-regime robust — 1d IC lower bound > 0 in both 2008–2021 and 2022–2026; **(2)** *tradability* at the traded 5d horizon is regime-contingent (discovery t=1.12 insignificant; hold-out t=2.41; split p=0.062). Lead with (1), present (2) as the limitation. Stop calling the post-2022 *improvement* the "cleanest evidence," and soften Table 4's "Positive OOS; significantly stronger" to "positive in both regimes; recent strength may be partly regime-driven."

### P1-B — Horizon incoherence: the endorsed signal (5d) and the only featured ML result (30d) cannot form one book, and the endorsed-horizon overlay is *untested* despite the model already existing
**Where:** §1 endorses **5d** momentum; §Results "Route B 30-day residual overlay" (lines 594–638) and Tables 5/6 feature a **30d** overlay; line 605 admits "a **5-day Route B overlay remains untested**"; line 252–255 admits 30d "is a selection step, not an exogenous design fact."
**Issue:** The two deliverable objects live at different horizons/rebalance frequencies, so they cannot be assembled into a single portfolio as presented. Worse, 30d was chosen *because* "residual structure and turnover looked most plausible" there (line 604) — i.e., selected on the outcome — while the **endorsed-horizon 5d overlay was never built**, even though `output/model_search/route_b_…fwd_5d__…xgb_balanced` is **already trained**. And the 30d audit rests on **N=35** non-overlapping periods (the weakest-powered horizon in the study), whereas the 5d test window has **223** non-overlapping periods (`momentum_regime_diagnostics.csv`) — ~6× the statistical power for the paired-increment test that currently returns t=0.25.
**Impact on the claim:** The paper's ML contribution is showcased at the one horizon that is both outcome-selected and least testable, while the horizon it actually recommends is left unexamined. A PM will read this as horizon-shopping.
**Fix:** Build the 5d Route B overlay (model exists; only the overlay-construction + paired-increment + DSR evaluation is missing — a few hours). Report it as the *primary* sleeve test at the endorsed horizon. Either it unifies the narrative (5d momentum benchmark + 5d residual sleeve = one combinable book with far tighter CIs) or it cleanly confirms momentum-only at 5d. Demote the 30d overlay to a horizon-sensitivity row.

### P1-C — Conviction/positioning: the contribution is real but the front matter leads with self-negation
**Where:** Abstract "Answer first" (lines 48–57); Conclusion (1049–1065).
**Issue:** The genuine, creditable deliverable — a reproducible **falsification/triage framework** (leakage controls, overlap correction, DSR/PBO/CPCV, factor-neutral attribution, PIT/capacity/borrow sensitivities) plus a decisive PM call (keep low-turnover momentum as an unfunded benchmark; spend the next dollar on point-in-time data, not models) — is present but arrives *after* a dense list of why nothing works. The page-1 answer reads as "I found nothing" rather than "I built a system that tells me what is and isn't fundable, and here is the decision."
**Impact:** Risks being scored as a no-alpha report rather than a high-rigor research-judgment artifact.
**Fix:** Open §1 with the framework-as-contribution and the decision, stated with conviction, *then* the supporting negatives. Pull capacity ($100M Sharpe 0.948) and momentum-correlation (0.93) into the answer-first paragraph so page 1 is self-contained. (This does not require any new overclaim — it is ordering.)

---

## P2 — Presentation (carried forward; still open)

- **Anchoring rows.** The two highest Sharpes in the paper — val-rejected LightGBM 30d **1.23** (Tables 5/6, lines 655, 806) and diagnostic λ=0.3 **1.20** (line 658) — sit un-greyed; a skimming PM anchors on them. Grey/footnote them and state once, near the table: *not validation-selected, below the 884-row null of 1.512, no DSR/PBO audit — shown only to avoid horizon-selective framing.*
- **DSR pair.** Leading with full-grid **DSR 0.003** (which the text admits pools 884 heterogeneous trials = a loose, inflated bound) over-signals precision. Lead instead with "**fails the 0.95 threshold under any trial count** (0.814 same-target, 0.003 full-grid)."
- **Capacity feasibility.** The $500M/$1B Sharpe rows (0.900/0.864) hold turnover fixed and are admittedly beyond the calibrated impact range; with the 10%-ADV ceiling at ~$395M, mark those rows "infeasible (p95 ADV 12.6%/25.3%)" rather than quoting a Sharpe.

## Highest-ROI experiments (hours, existing data only)
1. **5d Route B overlay (P1-B).** Model already trained; build overlay + paired-increment + DSR at the endorsed horizon. Highest value: fixes narrative coherence *and* multiplies test power (223 vs 35 periods).
2. **Cross-regime 1d IC statement (P1-A).** No new compute — both sub-period CIs already exist; restate the headline around "positive & significant in both regimes."
3. **IC decay / half-life curve** across the existing horizon grid — directly justifies endorsing 5d when significance peaks at 1d and fades by 20–30d. Still absent (cycle23 ask).
4. **Passive zero-skill yardstick** (equal-weight or random sector-neutral reference Sharpe) so the 0.62 has a frame. Still absent (cycle22/23 ask).
5. **One pooled pre-2022 traded-IC t-stat** from the four `momentum_regime_diagnostics/` slices — converts scattered "adverse in 2008–11/2017–21" cells into a single regime-robustness number.

## Wording / table / figure changes
- Reorder §1 to lead with framework-contribution + decision (P1-C); inject capacity + corr-to-momentum.
- Replace "cleanest evidence = post-2022 minus discovery" with the cross-regime-consistency framing (P1-A); soften Table 4 line 567.
- Grey/footnote LightGBM 1.23 and λ=0.3 rows; lead the DSR sentence with "fails 0.95 under any N."
- Add "infeasible" flags to $500M/$1B capacity rows.

## Residual risks (disclosed, not blocking)
- **Survivorship sign is genuinely unidentified and likely adverse** for a momentum book (missing delisted losers belong in the short leg). Only inclusion-side PIT + parametric haircut are possible here; PIT-filtered 5d Sharpe **0.461 (CI crosses zero)** is the correct, prominent "not fundable yet" anchor — keep it.
- **N=35 power.** Every 30d Route B statistic is underpowered to the point of indeterminacy; the honest read is "cannot distinguish from momentum," which P1-B's 5d rerun directly mitigates.
- **Full pipeline not one-command reproducible.** Route B models were trained on a GPU server and only the prediction/eval artifacts are mirrored locally (`docs/route_b_residual_alpha_20260622.md`, lines 9–11). Acceptable for a take-home; the report's *numbers* all reproduce from the mirrored artifacts, but CSV→trained-model is not runnable from the repo.
- **NW t rising with lag** (3.54→4.39→5.23) is correctly explained (negative IC autocorrelation), but rhetorically prefer leading with the conservative plain t=3.54 and citing NW as robustness.

**Net:** Submission-credible and above a median take-home on rigor. The gap to a *convincing* PM artifact is now two framing fixes (P1-A cross-regime reframe, P1-B horizon coherence) plus one cheap, high-power experiment (the 5d overlay) — not methodology, not reproducibility.
