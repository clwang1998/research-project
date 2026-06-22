I'll start by exploring the repository structure and reading the key files in parallel.

The main report is large. Let me read it in sections and explore the directory structure in parallel.

Let me continue reading the report and key docs in parallel.

Let me continue reading the report's results/discussion sections and the audit docs in parallel.

Let me read the remaining report sections and the triage/plan docs.

Let me read the report's discussion/conclusion and remaining docs.

Let me read the report's conclusion/limitations and check output summaries.

I've read the full report. Now let me verify key claims against artifacts and check the PDF page count (the plan flagged a ≤10-page constraint).

PDF is 10 pages (meets constraint). Let me verify the key numbers in the artifact CSVs.

Let me view the specific artifact files more precisely.

Numbers tie out well. Let me verify the regime, portfolio-uncertainty, and 2008–2021 split artifacts, plus check for any LaTeX reference errors.

All numbers tie out precisely. Let me verify the 2008–2021 traded-IC split claim and skim the reviewer-process doc.

All headline numbers reproduce exactly from artifacts. Let me do a final check on the leakage-control evidence (the one thing that would be a true P0) before writing the review.

I've reviewed the report and verified every headline number against `report/artifacts/` (all reproduce exactly), confirmed the PDF is 10 pages with no undefined LaTeX references, and checked the leakage, regime, PIT, capacity, and DSR/PBO evidence. Below is my read-only PM/senior-researcher review.

---

## Reviewer gate status
Copilot Opus reviewer **ran, read-only** (no edits, no commits). MCP `manual_review` was not invoked; this is a direct repository inspection. Scope: `report/sp500_case_study.tex` (+compiled PDF), the four audit/plan docs, and the `output/` + `report/artifacts/` summaries.

## Bottom line
**There are no P0 paper-killing blockers.** This is, if anything, an *under*-claiming paper: leakage controls are present, overlap inflation is corrected, failed methods (GAT/graph, Kronos, MLP, seed-bagging, Kaggle-aggregates) are honestly demoted to negative/ablation evidence and earn no alpha claim, and every number I spot-checked ties out to the artifacts. The issues are **framing/conviction** plus **one genuine logical soft-spot** (regime-circularity). These are P1/P2.

---

## Blocker findings

### P1-A — The central empirical pillar is regime-circular, and the paper never closes the loop
**Where:** §1 "Headline design" + §Results "signal-frequency"/Table 5 (momentum ladder) + §Discussion "Regime dependence".
**Issue:** The endorsed signal is 5-day sector-neutral momentum. Its *tradable-horizon* evidence is positive **only in the 2022–2026 hold-out**, which is itself a momentum-friendly regime:
- Traded 5d IC: hold-out block-boot t=2.41 (CI [0.004,0.042]) vs 2008–2021 t=1.12 (CI [−0.0045,0.0169], crosses zero). *(verified in `momentum_ic_traded_horizons_5d_split/`)*
- Portfolio 5d Sharpe by regime: **−0.95** (2008–11, mean-ret t=−1.90), 0.33 (2012–16), **−0.14** (2017–21), 0.62 (2022–26). At 30d the GFC Sharpe CI is **entirely negative** [−1.64,−0.027]. *(verified in `momentum_regime_diagnostics/`)*
- OOS 1d IC (0.0206) is **3× the discovery IC** (0.0066). OOS-stronger-than-IS is a regime-dependence flag, yet §Results frames it as "Signal survives; stronger OOS."

**Impact on the claim:** "Momentum is confirmed out of sample" is substantially "momentum worked in the one test regime that favored it." Every piece is disclosed, but they are never connected, and §1/Conclusion still call 5d momentum "the benchmark I would keep." A PM will read this as the paper's weakest logical seam.
**Fix:** Reframe to the honest conclusion the evidence supports — *no robustly tradable edge exists in this dataset; momentum is a literature-anchored benchmark whose tradable-horizon edge is regime-contingent (positive 2022–26, absent/negative 2008–11 and 2017–21).* Add the pre-2022-vs-post-2022 IC-equality test below to quantify it.

### P1-B — Headline answer is buried; no answer-first abstract
**Where:** §1 (first ~40 lines).
**Issue:** Despite `report_improvement_plan.md` P0-1, §1 is a dense wall of CIs and t-stats with no abstract. The "what I'd trade / Sharpe / capacity / drawdown / corr-to-momentum / next dollar" answer exists but is not skimmable in the 30 seconds a PM gives page 1.
**Fix:** Add a 4–6 line answer-first abstract; push the CI thicket into the existing evidence-ladder (Table 5).

### P1-C — Self-negating narrative tone
**Where:** Throughout §1, §Results, §Discussion.
**Issue:** Nearly every positive sentence is undercut in the same clause (the plan's own "叙事自我证伪" finding persists). Honest, but it (a) hides the thesis and (b) reads like a researcher arguing they found nothing.
**Fix:** State the strongest *defensible* claim cleanly first; consolidate caveats into one "Key risks" paragraph/box per section instead of per-clause hedging.

### P2 — Quality/credibility nits (non-blocking)
- **DSR/PBO wording (§Discussion, Table 7):** same-target DSR 0.814 is called "encouraging" — it still implies ~19% null-consistency in the *narrowest* search; PBO **50%** is effectively coin-flip overfit, arguably stronger than "adverse instability flag." Lead with "fails 0.95 under any trial count" and de-emphasize the precise-looking full-grid 0.003 (which the text itself admits is a loose heterogeneous bound).
- **Anchoring rows (Tables 2 & 6):** val-rejected LightGBM (Sharpe 1.23) and diagnostic λ=0.3 (1.20) are labeled but a skimmer anchors on them. Grey/footnote them.
- **0.620 vs 0.627 / arithmetic vs geometric returns:** disclosed, but reconcile in one footnote to avoid a "which is it?" reaction.
- **Real-estate vs result:** graph features still get a full feature-bullet + methodology subsection for a null result; compress to reclaim a half-page for the regime distribution (below).

---

## Highest-ROI experiments (all feasible in a few hours, existing data only)
1. **Pre-2022 vs post-2022 IC-equality test** for 5d momentum: block-bootstrap the *difference* in mean daily IC (you already have both series in `momentum_ic_robustness/` and the 5d split). This directly converts P1-A from a buried caveat into a number ("is OOS-stronger real or regime luck?").
2. **Leave-one-regime-out / CPCV Sharpe+IC distribution** for the momentum benchmark using the four `momentum_regime_diagnostics/` slices — report a *distribution and a pooled pre-2022 IC t-stat*, not just the friendly hold-out point estimate. This is the single change that most strengthens credibility.
3. **Add a passive yardstick:** equal-weight S&P / market-relative zero-skill Sharpe so the 0.62 momentum Sharpe has a reference frame (plan P2, cheap).
4. **IC decay / half-life curve** across the existing horizon grid to justify choosing 5d as the benchmark when statistical significance lives at 1d but tradability does not.

## Wording / table / figure changes for the final report
- Insert a 4–6 line **answer-first abstract** (signal → post-DSR economics → capacity → drawdown → corr-to-momentum → next dollar).
- Rewrite the §1 and Conclusion thesis sentence per P1-A (regime-contingent benchmark, not "confirmed OOS").
- Soften "Signal survives; stronger OOS" (Table 4 read-through) and add the regime-luck interpretation.
- Replace per-sentence hedging with one consolidated **"Key risks"** box in §Discussion.
- Grey/footnote the val-rejected high-Sharpe rows in Tables 2 & 6; reconcile 0.620/0.627.
- Swap ~½ page of graph/Kronos prose for a **regime IC/Sharpe distribution figure** (output of experiment 2).

## Residual risks (disclosed, not blocking)
- **Leakage controls rest partly on un-audited reruns:** `docs/data_leakage_review.md` (审查边界) states the purge/embargo/execution-lag fixes still need script-diff + run-output verification before counting as final no-leakage proof. The paper's "controls bind" claim is reasonable but not independently re-audited here.
- **Survivorship:** only inclusion-side PIT + parametric delisting haircut; correctly *not* claimed as a correction. PIT-filtered momentum Sharpe (0.461, CI [−0.49,1.43]) crossing zero is the binding "not fundable" reason — keep it prominent.
- **Dividend adjustment** uncertainty (minor, disclosed).

Net: methodologically this sits clearly above a median take-home and is submission-credible. The gap to a *convincing* PM artifact is conviction and the regime-circularity logic (P1-A/B/C), not rigor.
