I'll start by exploring the repository structure and reading the key files in parallel.

Let me explore the directory structure and read the key files in parallel.

This is cycle 25 of an iterative review process. Let me read the main paper and the most recent context files in parallel.

The cycle25 file is an empty placeholder. Let me read the paper structure and key sections in parallel.

Now let me read the paper in sections, starting with the abstract and key sections.

Let me continue reading the methodology and results sections.

Now the critical Results and Discussion sections.

Let me read the rest of the results, discussion, and conclusion.

The paper is remarkably thorough and self-critical. Now let me verify the numbers against the supporting docs and check the prior review cycle to see what's already been addressed.

The docs match the paper's numbers. Let me check the prior review cycles and remaining docs to understand what's already been addressed.

Now let me read the planning docs and check which carried-forward experiment gaps remain (5d overlay, IC half-life, passive yardstick).

Let me verify the PDF page count, modification times, and independently check key artifacts and whether the 5d overlay/IC-decay/passive-yardstick gaps remain.

PDF confirmed at exactly 10 pages. Critically, the **5d residual models are trained** (`...fwd_5d...xgb_balanced/metrics.json` exists) but **no 5d overlay backtest artifact exists** — confirming the endorsed-horizon overlay is still untested. Let me independently verify the load-bearing numbers and check the diff since cycle24.

Paired-increment numbers tie out exactly. The diff confirms cycle24's P1-A/P1-C/P2 items were addressed, but the 5d overlay remains unbuilt. Let me verify the now-headline cross-regime 1d IC pillar and the 5d split artifact.

All load-bearing numbers tie out exactly against the artifacts, including the now-headline cross-regime 1d IC pillar (discovery CI [0.0013, 0.0119] genuinely > 0; hold-out NW-21 t=4.39) and the 5d split. Let me do a final compile-integrity check (figures, undefined refs) before writing the review.

Verification complete. The PDF is clean (10 pages, all 6 figures present, no undefined references), every load-bearing statistic reproduces exactly from `report/artifacts/`, and the git diff confirms cycle24's framing fixes landed. The 5d Route B overlay remains the one genuinely untested object despite its models being trained. Here is my independent cycle-25 review.

---

## Reviewer gate status
Copilot Opus reviewer **ran read-only** via direct repository inspection (MCP `manual_review` not invoked in this runtime). **No files edited, nothing committed, no destructive commands.** Per the task's explicit "return findings only / do not edit files," I did not write to the cycle25 placeholder — findings are below for the orchestrator to archive.

**Verification done.** PDF compiles to exactly **10 pages** (meets the limit); all 6 figures present; no undefined refs/citations in the log; PDF newer than tex. Every headline statistic reproduces exactly from local artifacts:
- Cross-regime **1d IC** (the new headline pillar): discovery mean 0.00658, block-boot **t=2.42, CI [0.0013, 0.0119]** (lower bound >0); hold-out 0.0206, plain **t=3.54 / NW-21 t=4.39**, CI [0.0115, 0.0297]; split ΔIC 0.0141, p=0.0049 ✔
- **5d traded split**: discovery t=1.12 (CI crosses zero), hold-out t=2.41 CI [0.004, 0.042], ΔIC 0.0168 CI [−0.0045, 0.0380] p=0.062 ✔
- **Route B**: canonical IC 0.0279 vs 0.0282; paired t=0.25, corr 0.93, gap 0.246, CI [−0.17, 0.63]; DSR 0.814 (N=14) / 0.003 (N=884); PBO 50%; capacity 0.948/0.900/0.864; FM t=0.05; PIT 30d 0.987→0.725, momentum 5d 0.620→0.461 ✔

**All tie out.** Repro hygiene clean (no parquet/predictions tracked; `output/` gitignored).

## Bottom line
**No P0 paper-killing blockers.** This remains a rigorous, honestly *under*-claiming triage paper, clearly above a median take-home. It has **improved again since cycle24**: the momentum headline now leads with **cross-regime IC consistency** (not the weaker post-2022 *delta*), §1 now opens with framework-contribution + PM decision + capacity/correlation, capacity rows are flagged "infeasible," and the **1d discovery-vs-holdout split test the last three cycles asked for is now done** (p=0.0049). The remaining gap to a *convincing* artifact is **one cheap experiment the paper keeps writing around instead of running (P1-1)** plus presentation discipline.

---

## Blocker findings (paper-level)

### P1-1 — The endorsed-horizon (5d) Route B overlay is *still* untested — second cycle open, models already trained
**Where:** §Feature Eng. lines 262–264; §Results "Route B 30-day residual overlay" lines 607–618 ("a 5-day Route B overlay remains untested"); §Conclusion line 1070–1072. Models exist at `output/model_search/route_b_factor_residual_alpha_core_20260622__target_excess_sector_fwd_5d__tabular__xgboost__xgb_balanced/` (verified `metrics.json` present); **no** `route_b_*_5d` overlay/paired-increment artifact exists in `report/artifacts/`.
**Issue:** The paper endorses **5d** momentum but features its only ML result at **30d** — selected *because* "residual structure and turnover looked most plausible" there (line 258), on a sample of **N=35** non-overlapping periods (the weakest-powered horizon, where paired t=0.25 is uninformative). The 5d hold-out has **223** non-overlapping periods (`momentum_regime_diagnostics.csv`) — ~6× the power for the same paired-increment test. Since cycle24, the paper *added more disclosure language* ("until a paired 5d overlay audit is available, they should not be presented as one assembled book") **but did not run the 1-hour experiment**, even though the residual models are already trained. Writing around the gap twice is now itself a credibility signal a PM will notice.
**Impact on the claim:** The ML contribution is showcased at the one horizon that is both outcome-selected and least testable, while the horizon actually recommended is left unexamined. Reads as horizon-shopping.
**Fix:** Build the 5d overlay (`z(mom)+λ·z(5d residual-XGB)`, λ on validation Sharpe) and run paired-increment + DSR. Either it unifies the narrative (5d benchmark + 5d sleeve = one combinable book with far tighter CIs) or it cleanly confirms momentum-only at 5d. Demote the 30d overlay to a horizon-sensitivity row. This is the single highest-leverage remaining action in the study.

### P1-2 — The load-bearing significance lives at an *un-traded* horizon (1d t=4.39), and the curve linking it to the traded 5d book is still missing
**Where:** §1 lines 82–94; Table 4 (lines 566–591); §Results lines 539–564; §Discussion "Economic intuition" lines 1027–1032.
**Issue:** The cross-regime reframe is correct and now well-supported — but it means the paper's *cleanest* statistical pillar is the **1-day** IC (NW-21 t=4.39, both sub-periods >0), a horizon the paper does **not** trade, while the **5d** book it does endorse is significant *only* in the 2022–26 hold-out (discovery t=1.12 insignificant; split p=0.062). The paper asserts traded-IC "is positive at 5–10 days and marginal by 20–30 days" (line 1030) but shows **no IC-decay/half-life curve** to justify why 5d is the chosen trade horizon when significance peaks at 1d and the 5d edge is regime-contingent. This curve has been requested for three cycles and is still absent (no `*decay*`/`*half_life*` artifact).
**Impact:** A skeptical PM's first question — "your evidence is at 1d but you trade 5d; show me the horizon decay" — has no figure to answer it.
**Fix:** Add one IC-vs-horizon decay/half-life plot across the existing `{1,5,10,20,30}` grid (reuse `build_momentum_ic_robustness.py`; pure post-processing, no training). State the 5d choice as a power-vs-tradability trade-off explicitly, not as an assertion.

---

## P2 — Presentation (mostly carried; some new)

- **Abstract over-correction (new).** §1 lines 48–109 now swing from cycle22's "self-negating" to **stat-dense to the point of unreadability** — ~25 numbers on page 1 (5 t-stats, ~8 CIs, DSR×2, PBO, capacity, corr, three horizons × PIT haircuts). The genuine one-line decision ("keep 5d momentum unfunded; spend the next dollar on PIT constituents + delisting returns, not models") is buried. Lead with **one decision sentence + one compact evidence box** (signal-existence: 1d IC >0 both regimes; tradability: 5d regime-contingent; ML: no distinguishable increment), then move the number-thicket to the body.
- **DSR ordering.** The abstract (line 59) and Table 7 (line 726) still lead with full-grid **DSR 0.003**. Note the N=884 expected-max null Sharpe is **1.512** — above momentum (0.74), the overlay (0.987), *and* LightGBM (1.23), i.e. it mechanically deflates **everything**, so it certifies nothing and looks like guaranteed deflation rather than a diagnostic. Lead consistently with the same-target **DSR 0.814 (N=14)** as the like-for-like number and cite 0.003 as "conservative bound; fails 0.95 under any N" (the Discussion already phrases it this way at line 897 — propagate it to the abstract and table).
- **Anchoring rows.** LightGBM 30d **1.23** and λ=0.3 **1.20** are now labeled "diagnostic only / not a result" (Tables 5–6, lines 669/672/820) — good — but remain ungreyed; a skimming PM still anchors on the two highest Sharpes in the paper. Grey them or move to a footnote.

## Highest-ROI experiments (hours, existing data only)
1. **5d Route B overlay + paired-increment + DSR (P1-1).** Models trained; only overlay construction + eval missing. Fixes narrative coherence *and* multiplies test power 6× (223 vs 35 periods). **Do this first.**
2. **IC-decay/half-life curve across the horizon grid (P1-2).** Pure post-processing; directly answers the 1d-vs-5d horizon question a PM will probe.
3. **Passive / zero-skill yardstick** (equal-weight or random sector-neutral reference Sharpe) so the 0.62 has a frame. Requested cycles 22–24; still absent; cheap.
4. **One pooled pre-2022 traded-IC t-stat** from the four `momentum_regime_diagnostics/` slices — converts scattered "adverse in 2008–11/2017–21" cells into a single regime-robustness number.

## Wording / table / figure changes
- Replace the dense page-1 thicket with one decision sentence + a 3-row evidence box (P2).
- Lead DSR with same-target 0.814; frame 0.003 as "conservative bound, fails 0.95 under any N"; note the 1.512 null deflates all rows (P2).
- Grey/footnote the LightGBM 1.23 and λ=0.3 1.20 rows (P2).
- After running P1-1, demote the 30d overlay to a sensitivity row and make the 5d overlay the primary sleeve test.
- Add the IC-decay figure (P1-2).

## Residual risks (disclosed, not blocking)
- **Survivorship sign genuinely unidentified and likely adverse** for a momentum book (missing delisted losers belong in the short leg). Only inclusion-side PIT + parametric haircut possible here; PIT-filtered 5d Sharpe **0.461, CI [−0.49, 1.43] crosses zero** is the correct, prominent "not fundable yet" anchor — keep it foregrounded.
- **N=35 power.** Every 30d Route B statistic is underpowered to indeterminacy; honest read is "cannot distinguish from momentum." P1-1's 5d rerun directly mitigates.
- **Pipeline not one-command reproducible.** Route B models were GPU-trained; only prediction/eval artifacts are mirrored locally (`docs/route_b_residual_alpha_20260622.md` lines 9–11). Acceptable for a take-home — all *reported numbers* reproduce from mirrored artifacts — but CSV→trained-model is not runnable from the repo; state this once.
- **Dividend adjustment** uncertainty (minor, disclosed).

**Net:** Submission-credible and clearly above a median take-home on rigor; numbers and reproducibility are not the constraint. The gap to a *convincing* PM artifact is now **one cheap, high-power experiment (the 5d overlay, P1-1)** plus the IC-decay curve (P1-2) and tighter page-1 communication — not methodology, not data integrity.
