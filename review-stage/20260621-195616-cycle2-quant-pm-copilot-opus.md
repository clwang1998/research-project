I'll review this as a quant PM reviewer. Let me start by exploring the repository structure and reading the key files.

The report is large. Let me read it in sections and explore the directory structure in parallel.

Let me continue reading the paper and key documents in parallel.

The Route B doc is honest about weaknesses. Let me continue reading the rest of the paper and the audit documents.

Let me read the rest of the paper and the triage/improvement plan docs.

Let me finish reading the paper and the report improvement plan.

I have a thorough view of the paper now. Let me verify the output artifacts support the claims and check the reviewer doc and PDF.

Let me verify the key headline numbers against the actual artifact files.

Numbers largely match the artifacts. I found an important internal inconsistency in the rank-IC sign. Let me verify the page count, the overlay's rank-IC provenance, and the original task spec.

Let me read the route_b run's own metrics/summary and try to extract the task spec and page count.

12 pages — over the 10-page guideline. Let me confirm the task spec's page limit and read the route_b rank-IC details.

Confirmed: **hard 10-page limit, but the PDF is 12 pages.** Let me reconcile the rank-IC table values from the run's own summary.

Confirmed a concrete inconsistency: in the **same route_b run** that underlies the overlay, the momentum baseline's rank IC is **−0.0105**, but the paper's Table 6 reports **+0.0282** for it. Let me verify the other main results table's provenance and the survivorship treatment, then I'll write the review.

I've completed a thorough read of the report, the supporting docs, and the underlying `output/` artifacts, and I verified the headline numbers against the raw files. Here is my review.

---

# Copilot Opus — Read-Only Quant PM / Senior Researcher Review

**Verdict: there ARE blocking paper-level issues.** The methodology is genuinely above-average (strong leakage controls, overlap-adjusted ICIR, DSR/PBO/CPCV, honest negative controls). But the submission is blocked by a hard format violation, a headline that over-reads a statistically-rejected result, a horizon-selective benchmark framing, and a rank-IC traceability inconsistency. All are fixable in a few hours without new modeling.

## Blocker findings

### P0 — Format (will get the report penalized/truncated)
**P0-1. Over the hard 10-page limit.** `MLP_research_project.pdf` states "submit a PDF case study report, with a maximum of 10 pages." The committed `report/sp500_case_study.pdf` is **12 pages** (verified via pypdf). `docs/report_improvement_plan.md` already flagged 11pp; it has grown, not shrunk.
- *Impact:* a grader may stop at page 10 or mark it down before judging the science.
- *Fix:* compress to ≤10. Move the graph-ablation table (`tab:negative_ablations`), the earlier 10d overlay (`tab:residual_overlay`), and the sleeve-book table to one-paragraph summaries; reduce GAT/Kronos/MLP to ≤1 sentence each in the body. That alone recovers ~2 pages.

### P1 — Paper credibility (fix before submission)
**P1-1. The headline over-reads a 35-observation, drawdown-driven, statistically-rejected result.** §1 "Headline design" and §Results "Route B 30-day residual overlay" lead with "improves hold-out Sharpe and drawdown." But the supporting evidence (verified in `output/alpha_robustness_audit_route_b_30d/`):
- Sharpe 0.74→0.99 and DD −13.8%→−7.3% rest on **N=35 non-overlapping 30d periods** (`selected_signal_metrics.csv`, `periods=35`).
- Bootstrap Sharpe CI **[0.019, 1.796]** (essentially touches zero); full-grid **DSR=0.003**; **PBO=50%**; FM t=0.05; ΔRankIC = **+0.0001** (negligible).
- *Impact:* the central positive claim is not supportable at submission grade; the "improvement" is one-path drawdown luck on a momentum-friendly regime.
- *Fix:* reframe headline deflation-first — "no statistically robust improvement over momentum; at best a candidate risk-timing sleeve" — and print N=35 + the bootstrap CI directly next to the Sharpe/DD numbers in `tab:route_b_30d`.

**P1-2. Horizon-selective benchmark framing hides the strongest raw result.** Table 7 (`tab:results`) shows only 5d/20d, where momentum wins, and **omits 30d** — yet its own cited source `docs/horizon_comparison.md` shows 30d sector **LightGBM Sharpe 1.23 / IC 0.036, XGBoost 1.21 / 0.032, Ridge 1.17 / 0.026**, all beating the 30d momentum baseline (0.740 / 0.0282) *and* the headlined Route B overlay (0.987).
- *Impact:* "momentum is hard to beat" is a 5d-specific claim presented as general; the strongest raw 30d model wins are not shown, and the headline uses a *weaker* construction than the appendix already contains. A PM will spot this immediately.
- *Fix:* add a 30d block to Table 7 with momentum + best plain 30d model + Route B overlay, each annotated with DSR/PBO/turnover, and state explicitly why the sleeve is preferred despite lower raw Sharpe (turnover 0.62–0.70 vs 0.40; fails deflation even harder; economic role).

**P1-3. Rank-IC artifact inconsistency undermines the "internally traceable" claim.** §Results "Route B artifact check" says the 30d momentum row "reproduces exactly." It does for Sharpe/return/turnover/DD — but **not for rank IC**:
- The route_b run that the overlay is built on reports momentum baseline rank IC = **−0.0105** (`output/model_search/route_b_…__30d__tabular__xgboost__xgb_balanced/baseline_score_test_rank_ic.csv` and `summary.md`), vs **+0.0282** in Table 6 and the baseline JSON.
- The audit's `selected_signal_metrics.csv` reports the overlay rank IC as **−0.0083**, vs **+0.0283** in Table 6.
- *Impact:* a reviewer opening the artifacts sees a *negative* momentum IC contradicting Table 6; "internally traceable" is overstated for the IC column (sign/target conventions differ across evaluators).
- *Fix:* standardize one evaluator/target for rank IC, recompute the run's baseline/overlay IC, or annotate the convention. The economic numbers are consistent and the qualitative claim ("RankIC barely changes") survives — but the column must be reconciled.

### P2 — Honesty tightening
- **P2-1. Factor-neutral framing oversells** (`tab:p0audit`, §Discussion): "Factor-neutral Sharpe 1.006 — economics survive" alongside FM t=0.05 and neutral IC≈0 is contradictory; a higher neutral Sharpe with zero IC is consistent with noise, not orthogonal alpha. Lead that bullet with FM t≈0 / no independent alpha; treat 1.006 as non-informative.
- **P2-2. Adj-Close provenance** (§Data): the task spec lists an "Adj Close" column, but the shipped file had only `close`. State that the schema differed and that you verified `close` is split-adjusted (your NVDA/AAPL audit) — one sentence preempts a grader assuming you ignored adj_close.

## Focused experiments that would most improve the report (a few hours, current data only)
1. **Deflate the plain 30d models.** Run DSR/PBO/turnover on the 30d LightGBM/XGBoost/Ridge already in `horizon_comparison.md` (pure post-processing of `output/`). This either kills the "models beat momentum at 30d" concern or forces it into the open — directly resolves P1-2.
2. **Reconcile the rank-IC evaluator** (resolves P1-3): recompute momentum + overlay rank IC under the `eval_momentum_baseline.py` convention for the route_b run; overwrite the audit CSV so all rank ICs share one sign.
3. **Surface sample size + SE everywhere:** print N (non-overlapping periods) and per-period Sharpe SE next to each hold-out Sharpe; add the bootstrap CI to Table 6.
4. **CPCV/regime Sharpe distribution for the Route B overlay** (data supports it): report the fraction of CPCV folds where the overlay beats momentum, instead of resting the headline on the single 2022–2026 path.

## Wording / table / figure changes for the final report
- §1 "Headline design": replace "improves hold-out Sharpe and drawdown … before selection deflation" with a deflation-first sentence; add N=35.
- `tab:route_b_30d`: add bootstrap Sharpe CI + N; footnote that ΔRankIC = +0.0001 is within noise; add the best plain-30d-model row.
- `tab:results`: add a 30d block; annotate every model row with DSR/PBO.
- `tab:p0audit`: reorder so FM t≈0 precedes factor-neutral Sharpe.
- GAT / Kronos / MLP: compress to ≤1 sentence each in the body (helps both the page limit and claim honesty).
- Reorganize Results answer-first: the one positive result is currently buried among many negatives with a horizon switch mid-section.

## Credit where due (do not lose these in the rewrite)
Strong, rarely-seen rigor: 1-day lag + two-sided purge + embargo + train-only fit + pre-split winsorization (with a no-embargo diagnostic confirming the controls bind); overlap-adjusted ICIR + Sharpe>3/ICIR>5 gate; pre-registered single-factor frequency scan with OOS confirmation (Table 3); honest negatives (graph placebo ≥ real edges, MLP demoted, seed-bagging and Kaggle aggregates fail, sleeve-book fails). 64 in-text t-stat/CI/DSR references — the earlier "no t-stats" critique is addressed.

## Residual risks (disclose, not blockers)
Survivorship uncorrected (haircut sensitivity only, not PIT constituents/delisting returns); single hold-out regime; capacity/short-side liquidity bind by ~$500M–$1B; neutralization is OHLCV+sector only (no true size/value/quality factor model).

---

**Reviewer-gate note (per `AGENTS.md`):** The Copilot Opus read-only paper review **ran** (this pass), inspecting the `.tex`, the supporting `docs/`, and the underlying `output/` artifacts. **Outcome:** no fatal leakage/methodology defect, but **blocking issues exist** — one P0 format (10-page limit) and three P1 claim-discipline/traceability items — all fixable without new modeling. I made **no file edits** and ran no destructive/commit commands. Remaining test gap: I could not recompile the PDF locally (no LaTeX toolchain present), so the page count is from the committed PDF; re-verify after trimming.

