I'll review this as a quant PM/researcher reviewer. Let me start by exploring the repository structure and reading the key files.

Let me read the main report and key supporting docs in parallel.

The Route B doc is refreshingly honest. Let me read the main report in sections plus the other key audit docs.

Let me continue reading the report and the triage/improvement docs.

Let me read the results and discussion sections of the report — the critical parts for the claim discipline.

I've read the full report. Now let me check the improvement plan, reviewer doc, and verify the output artifacts that back the key claims.

Now let me verify the key numbers against the actual artifacts. Let me check the momentum baseline JSON, the paired increment artifact, and report artifacts.

Momentum baseline matches exactly. Let me verify the Route B audit details and the paired-increment artifact that backs the central "t=0.25" claim.

Numbers tie out. Let me verify the paired-increment summary and the factor-neutral/Fama-MacBeth artifacts, plus check the report's PDF page count.

All artifacts tie out precisely. Let me check the figures, PDF page count (the plan flagged a 10-page limit), and the reviewer MCP doc.

Let me check the LaTeX log for the page count and review what prior review rounds found.

The PDF is exactly 10 pages — within limit. There's an extensive review history. Let me read the most recent review cycles to avoid repeating prior findings and focus on what's still open.

The prior cycle (5) already addressed the ICIR-bold, LightGBM-labeling, and paired-increment findings — and I've confirmed those fixes are in the current `.tex`. This is cycle 6, so I need to find what's genuinely still open. Let me verify the LightGBM row provenance and the momentum significance symmetry question.

The "all runs" table is revealing. Let me read the leakage-validation doc and locate the momentum per-period stream so I can compute momentum's own significance (the symmetry question) read-only.

Leakage controls are properly validated via synthetic purge/embargo tests. Now let me compute, read-only, the momentum baseline's own significance (the symmetry gap I suspect) and independently cross-check the paired increment.

My calculations confirm the paired test exactly (t=0.248, corr=0.932). And they surface a genuinely new finding: the **momentum baseline's own 30d Sharpe (0.740) has a bootstrap 95% CI of [−0.22, 1.82] — it crosses zero (t=1.51)**. Let me confirm the report doesn't already address this symmetry, and whether it makes the "1.23 < 1.512 expected-max-null" argument.

I now have everything I need. All headline numbers reproduce exactly from the archived artifacts, the leakage controls are validated with synthetic purge/embargo tests, and the prior cycle-5 fixes (paired-increment row, unbolded ICIR, LightGBM labeling) are correctly in the current `.tex`. I also computed one decisive new statistic. Here is my read-only review.

---

# Copilot Opus Reviewer — Senior Quant PM Assessment (Cycle 6)

**Verdict: No P0/P1 paper-level blockers.** This is an honest, well-instrumented *deflation-first / triage* study. The headline ("12–1 momentum is the only robust signal; the 30-day residual overlay is an exploratory volatility/drawdown sleeve that fails production-grade deflation") is supported and reproducible. I verified the momentum baseline JSON, Route B DSR/PBO/paired-increment, factor-neutral, capacity, and survivorship CSVs against the `.tex` — they tie out. The remaining issues are **claim-symmetry and presentation**, not correctness. Cycle-5 findings (P1-A ICIR bold, P1-B LightGBM label, P2-C paired test) are correctly resolved.

## Blocker-style findings (all P2)

### P2-1 (NEW, highest value) — Asymmetric rigor: momentum's *own* hold-out Sharpe is never deflation-tested
*Files:* `report/sp500_case_study.tex` Results L484–495, Headline L66–74, Conclusion L913–922.

The paper deflates the overlay exhaustively (DSR, PBO, paired-t, bootstrap CI) but applies none of that to its headline positive. I computed it read-only from the archived per-period stream (`…__xgb_balanced/baseline_score_test_backtest.csv`, N=35):

| Momentum 30d baseline | Value |
|---|---|
| Net Sharpe | 0.740 |
| t-stat on mean per-period return | **1.51 (not sig. at 5%)** |
| i.i.d. bootstrap 95% Sharpe CI | **[−0.22, 1.82] — crosses zero** |
| P(Sharpe > 0) | 0.94 |

**Impact:** "Momentum is the only *robust* signal" is, on the same N=35 hold-out, **statistically indistinguishable from zero** as a portfolio. The claim actually rests on the single-factor IC t-stat (3.54, Table `tab:frequency_confirm`) plus literature — which is fine, but the paper never says so, so a PM sees a double standard (overlay charged DSR/PBO; benchmark gets a pass). **Fix:** add the momentum baseline's bootstrap CI/t-stat next to the overlay's, and state explicitly that momentum's robustness is anchored on the daily IC t-stat (3.54) + prior literature, **not** the thin 30d portfolio Sharpe.

### P2-2 (NEW) — The 30d results block hides the *actually selected* model and shows the *non-selected* best number
*Files:* `tab:results` 30d block L784–786; `docs/horizon_comparison.md` L67–68.

At 30d-sector the validation rule selects **MLP** (val ICIR 0.488); its OOS Sharpe is **0.69 < momentum 0.74**. The table instead prints the **non-selected LightGBM** (val ICIR 0.08, Sharpe 1.23). The 5d block shows the val-selected MLP losing to momentum — but the 30d block omits the val-selected MLP and anchors the reader on the best unaudited line. **Impact:** weakens the overfitting thesis exactly where it's strongest. **Fix:** add the val-selected MLP 30d row (Sharpe 0.69 < 0.74) — it directly reinforces "validation edge does not survive."

### P2-3 (NEW, one-sentence win) — LightGBM 1.23 is never measured against the paper's own null
*Files:* L567–572.

The report makes the "0.987 < 884-trial expected-max-null 1.512" argument for the overlay but not for LightGBM, even though **1.226 < 1.512** too. **Fix:** one clause — "even this unaudited row sits below the 884-trial expected-max-null Sharpe of 1.512" — cleanly neutralizes the visually-best anchor without archiving its stream (stronger than the current "lacks archived DSR/PBO artifacts").

### P2-4 (carried from cycle 5, still unfixed) — `tab:results` mixes target families across horizons
*Files:* L780–782, caption L766–768.

5d/30d are sector-relative; 20d is **market-relative**, where momentum looks best (RankIC 0.042, Sharpe 0.82). Disclosed in caption but reads as horizon×family cherry-picking. **Fix:** standardize to sector-relative (20d-sector momentum/LightGBM numbers exist in `horizon_comparison.md`) or add a per-row family flag + one-line justification.

## Focused calculations that most improve the report (each ≤ minutes–2 hrs)
1. **Momentum baseline bootstrap CI + t-stat** (done above: [−0.22, 1.82], t=1.51) → drop into Results/`tab:route_b_30d` as a symmetry row. *Highest ROI.*
2. **Add val-selected MLP 30d row** (0.69) to `tab:results` — data already in `horizon_comparison.md`.
3. **Hold-out-specific survivorship bound:** count actual 2022–2026 S&P 500 delistings (very few → headline impact small) instead of a uniform 2%/yr haircut; conversely note the uniform haircut *understates* crisis-clustered short-leg damage for any full-history claim.
4. **Block/stationary bootstrap** for all absolute Sharpe CIs (current i.i.d. resample over 35 autocorrelated 30d periods overstates precision).

## Wording / table / figure changes
- **Headline (L66–74) & Conclusion (L913–922):** anchor "momentum is robust" on IC t=3.54 + literature, and acknowledge the N=35 30d momentum Sharpe is itself CI-crossing-zero. This is the single most important honesty upgrade.
- **`tab:results`:** add MLP 30d row; standardize/justify the 20d family; optionally annotate LightGBM "< 1.512 null."
- **Factor attribution (L836–846):** state plainly that neutralization *raises* Sharpe (0.987→1.006) while halving return (8.27%→5.17%) and lifting turnover (0.49→0.70); the demotion rests on **FM t=0.05 + negligible RankIC**, not a Sharpe drop (still slightly hand-wavy — carried from cycle 5).
- **Keep as-is (genuinely good):** placebo-graph-beats-real-graph ablation, MLP demotion, Kronos-as-future-data-route framing, seed-bag/Kaggle-agg negative controls, overlap-adjustment treatment.

## Residual risks (no blockers)
- **Survivorship bounded, not corrected** (no PIT constituents/delisting returns); momentum is precisely the signal it most flatters, so the haircut is a floor.
- **N=35 → very low power**; every 30d conclusion is fragile (now partly explicit via the paired test).
- **Cross-evaluator RankIC sign flips** (canonical positive vs audit −0.0083) reconcile on economics but remain a reproducibility smell — a single canonical end-to-end evaluator would remove the last audit ambiguity.

**Process note:** Read-only review per `AGENTS.md`/`docs/copilot_opus_reviewer_mcp.md`. No files edited. The `manual_review` MCP tool is not exposed in this runtime, so this is the direct paper-first Opus review; it should be saved under `review-stage/` per the gate. Findings only.
