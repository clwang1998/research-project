I'll start by exploring the repository structure and reading the key files in parallel.

Let me read the main report and key docs. The .tex is large, so I'll read it in sections alongside the other documents.

Let me continue reading the report body and the remaining docs.

Now let me read the rest of the report (results, robustness, discussion, conclusion) and check output summaries.

Let me read the remaining report sections and check the output summaries.

Now let me verify key claims against the output artifacts and check the PDF page count.

Momentum baselines match the report exactly. Let me verify the Route B overlay and robustness-audit artifacts.

Route B paired-increment and canonical-IC numbers all reconcile. Let me verify the DSR/PBO audit artifacts and confirm all referenced figures exist.

All audit numbers reconcile with the artifacts. Let me do a few targeted consistency checks before finalizing.

I've verified all headline numbers against the artifacts — they reconcile cleanly. Here is my review.

---

# Copilot Opus — Read-Only Quant PM / Senior Researcher Review
**Deliverable reviewed:** `report/sp500_case_study.tex` (compiles to 10 pages, meets the ≤10 limit) plus supporting `docs/` and `output/` artifacts.

**Reproducibility spot-check (passed):** Momentum baselines (`output/momentum_baseline_priority/*.json`), the Route B overlay, paired-increment (`report/artifacts/route_b_paired_increment/`), canonical IC (`route_b_canonical_ic/`), and the full P0 audit (`output/alpha_robustness_audit_route_b_30d/`: DSR 0.003/0.814, PBO 0.50, FM t=0.048, capacity, survivorship) all match the numbers printed in the paper. All six referenced figures exist. **No fabricated or unreproducible headline number found.**

---

## Blocker findings

### P0 — none
There is **no blocking paper-level integrity issue.** No leakage, horizon-misalignment, sample-boundary, or overclaim defect that invalidates a headline. The report is unusually honest: it does not claim ML beats momentum, frames Route B as drawdown-dampening rather than alpha, and demotes graph/GAT/MLP/Kronos/seed-bag honestly. If anything it *under*-claims. The remaining issues are judgment/framing, not correctness.

### P1-1 — The endorsed benchmark contradicts its own regime evidence
- **Where:** §1 (l.66–105) endorses "keep the 5-day sector-neutral momentum book"; §Discussion regime (l.996–999) shows 5d momentum Sharpe **−0.95 / +0.33 / −0.14 / +0.62** across 2008–11 / 2012–16 / 2017–21 / 2022–26. The only positive regime is the hold-out that produces every headline number. PIT inclusion cuts 5d Sharpe 0.62→0.46 (CI [−0.49,1.43], crosses zero); mean-return t=1.31.
- **Impact on claim:** The standalone *portfolio* case is effectively fitted to the one momentum-friendly regime in the sample. Endorsing "the benchmark I would keep" on a book that loses in 3 of 4 slices is the kind of circularity a PM flags immediately. Verified in `report/artifacts/momentum_regime_diagnostics/` (the 2009 momentum crash: −19.3%, −14.0% periods are real).
- **Fix:** Re-anchor conviction *explicitly* on IC + external literature and state plainly that the portfolio Sharpe is regime-confined to 2022–26. Stop implying the book itself is robust. One sentence: "I would size off IC stability, not this Sharpe, because the portfolio only clears in the recent regime."

### P1-2 — The load-bearing significance stat is horizon-mismatched
- **Where:** The strongest number in the paper — NW lag-21 **t=4.39**, IC CI [0.0115,0.0297] (l.831, Table `tab:momentum_ladder`) — is a **1-day** daily IC (`momentum_ic_robustness.csv`, `target_excess_sector_fwd_1d`). The tradable signal is 5–30d, where block-bootstrap IC intervals **cross zero at 20d/30d** (l.534–536).
- **Impact:** Momentum's "it exists" pillar rests on a horizon nobody trades at |IC|≈0.01, while the traded-horizon evidence is marginal. A skeptic reads this as the strong stat carrying weight it shouldn't. The counterintuitive NW-tightening (plain 3.54 → lag-21 4.39 → lag-63 5.23) is asserted in one line (l.537–540) but not shown.
- **Fix:** Demote the 1-day t to "signal-existence" evidence explicitly (already partly done at l.93–95, but the conclusion l.1053–1056 still leads with it). Add the IC autocorrelation function as a small panel, or soften the HAC claim to "robust to, not strengthened by, autocorrelation."

### P1-3 — Self-defeating narrative undercuts the deliverable
- **Where:** Throughout §Results/§Discussion; this was the explicit target of `docs/report_improvement_plan.md` (§2.8 "叙事自我证伪"). Structure improved (headline-first §1, Route B as sleeve), but nearly every positive result is killed in the same sentence it appears.
- **Impact:** For a take-home, this risks reading as "candidate found nothing" rather than "candidate has the judgment to know what's real." Conviction is the stated gap; it's still thin.
- **Fix (presentational):** Consolidate the repeated kill-shots into one robustness verdict box. Lead each result with the *decision* it drives. End §1 with one unhedged sentence: the single thing the author would paper-trade, at what capacity, and the one experiment that would change the call.

### P2-1 — DSR verdict hinges on an arbitrary trial count
- `multiple_testing_dsr.csv`: same-target DSR **0.814** (N=14) vs full-grid **0.003** (N=884) — identical Sharpe/σ, only N differs. The entire "not deflated alpha" verdict turns on choosing 884. Paper concedes it pools heterogeneous horizons (l.879–881) but never justifies *why 884 is the family*. **Fix:** one sentence defending 884 (or report a same-horizon N as the primary, 884 as a conservative bound).

### P2-2 — Unreconcilable in-text number
- l.610: "validation ICIR **0.0804** versus the selected MLP's **0.4882**" — these don't match any other ICIR scale in the paper (elsewhere 0.7–1.2). Reads as inconsistent. **Fix:** label the exact metric (walk-forward mean val ICIR for the Route B split?) or correct it.

### P2-3 — Minor annualization drift
- Momentum 30d ann-return is **7.78%** (canonical JSON, used in Table `tab:route_b_30d`) but **7.48%** in `route_b_paired_increment` (8.4 rebal/yr). Sharpe matches to 10 decimals, so harmless, but two conventions coexist. **Fix:** state the annualization factor once and apply uniformly.

### P2-4 — Best-looking number is an unaudited row
- Table `tab:results`: the 30d LightGBM "validation-rejected; unaudited" row shows **Sharpe 1.23 / 13.0%** — the most attractive cell in the table. A skimming PM anchors on it. **Fix:** gray it / footnote-flag it more prominently as not validation-selected and not in the DSR family.

---

## Focused experiments that would most improve the report (each ≲ a few hours, current data only)

1. **CPCV / combinatorial-purged Sharpe distribution for the 5d momentum book** (highest ROI). The paper repeatedly says "calendar slices, not CPCV proof" (l.1000) and concedes no pre-2022 overlay distribution exists. Momentum is no-fit, so it can be recomputed on every CPCV path → converts P1-1's four point estimates into a Sharpe distribution and directly answers "single lucky regime."
2. **Retrain the Route B residual model on ≥2 earlier walk-forward splits** to produce even a coarse 2008/2020 overlay Sharpe. The drawdown-dampening claim only matters in a stress regime; right now it's never tested in one.
3. **Bootstrap CI on the canonical RankIC gap (overlay − momentum, 0.0279 vs 0.0282).** Turns "within evaluator noise" (l.40, l.605) into a number; cheap from existing predictions.
4. **Cost break-even curve for the overlay.** Overlay turns 0.49 vs momentum 0.40 for a t=0.25 increment — find the per-side cost at which the 0.25 Sharpe gap vanishes. One curve settles whether the only benefit (drawdown) is cost-fragile.

## Wording / table / figure changes for the final report
- §1 and §Conclusion (l.1024–1073): add one **conviction sentence** (what you'd trade, sizing basis, kill-criterion); state the portfolio Sharpe is regime-confined.
- Add a single **"Robustness verdict"** box; remove per-paragraph re-hedging.
- Fix the **0.0804/0.4882** label (P2-2); add one sentence justifying **N=884** (P2-1); unify the **7.78%/7.48%** convention (P2-3); visually demote the **unaudited LightGBM** row (P2-4).
- Table `tab:momentum_ladder`: relabel the 1-day NW t-stat row as "signal existence (non-traded horizon)" so it isn't read as trading significance.

## Residual risks (acknowledged, not blocking)
- **N=35 non-overlapping periods** underlies every Route B economic claim — honestly disclosed but irreducibly thin.
- **Survivorship is inclusion-side only**; delisting side is parametric. Direction (adverse for a loser-short book) is stated; magnitude is not bounded.
- **DSR family-size** remains a judgment call, not a theorem (paper says so).

**Bottom line:** Submit-ready on integrity and reproducibility; **not** blocked by any P0. The work's weakness is conviction and the regime-confined portfolio evidence behind the endorsed benchmark (P1-1/P1-2), plus a narrative that argues against itself (P1-3). Fixing those three — ideally backed by experiment #1 (CPCV) — is what moves this from "rigorous triage" to "credible PM-facing research."

*(Read-only review: no files were edited, no commands beyond inspection were run.)*

