I'll review this as a senior quant PM. Let me start by exploring the repository structure and reading the key files.

The repository is large. Let me read the report in sections and explore the directory structure in parallel.

Let me continue reading the report and key documents in parallel.

Let me continue reading the report's results sections and the key audit documents.

Let me read the remaining report sections (results tables, discussion) and the triage/improvement docs.

Let me read the rest of the report (remaining tables, discussion, conclusion) and the improvement plan.

The report is a "deflation-first" negative-result paper. Now let me verify the key numbers against the output artifacts and check internal consistency.

Let me verify the key Route B audit numbers against the actual output artifacts.

Numbers are corroborating well. Let me verify the factor-attribution, capacity, and survivorship CSVs, and trace where the overlay's RankIC/ICIR (0.0283/0.768) come from.

Let me trace the overlay ICIR source (0.768), confirm per-period returns are archived, and read the survivorship/leakage/reviewer docs.

Per-period overlay returns are archived (35 rebalances). Let me confirm the momentum per-period stream exists for a paired test, and read the survivorship/leakage/reviewer docs.

Let me check the running shell, look for an archived momentum per-period stream, and check the PDF page count and reviewer doc.

I have what I need to run the single most valuable check myself: a **paired test of the overlay vs momentum per-period returns** (both streams are archived). Let me compute it read-only.

Both streams have 35 aligned periods. Let me compute the paired difference test, per-stream Sharpes, and a paired bootstrap on the Sharpe gap.

The paired test is decisive. Let me verify the PDF page count (the ≤10-page constraint is flagged as a hard issue) and confirm the unaudited LightGBM row's status.

PDF is 9 pages — within the 10-page limit (the improvement plan's page concern is resolved). Let me confirm the unaudited LightGBM 30d row's provenance.

Let me confirm the column headers so I correctly characterize that LightGBM row's validation ICIR.

Let me confirm the report doesn't already contain an incremental/paired significance test before I flag it as missing.

I've completed a full read-only review: I read the report source, the Route B / P0 audit / triage / improvement-plan / leakage / survivorship docs, verified the headline numbers against the archived CSVs, traced the IC/ICIR convention mismatch, confirmed the 9-page PDF, and computed the one missing decisive statistic (paired overlay-vs-momentum test) from archived per-period streams.

# Copilot Opus Reviewer — Senior Quant PM Assessment

**Verdict: No P0 blockers.** The paper is an honest, well-instrumented *deflation-first / triage* study, and its core claims are credible and reproducible from the archived artifacts. The headline ("momentum is the only robust signal; the 30d residual overlay is an exploratory risk-sleeve that fails production-grade deflation") is supported. The issues below are presentation/consistency problems and one high-ROI missing statistic — fixing them makes the paper *stronger and more honest*, not less.

---

## Blocker-style findings

### P1-A — Headline 30d table mixes evaluator conventions and **bolds a cross-convention ICIR "win"**
*Files:* `report/sp500_case_study.tex` Table `tab:route_b_30d` (L568–588) + L590–604; `docs/route_b_residual_alpha_20260622.md` (L27–31); `output/alpha_robustness_audit_route_b_30d/selected_signal_metrics.csv`.

- The table prints the overlay as RankIC ≈0.028 / **ICIR ≈0.77 (bolded)** vs momentum 0.0282 / 0.698, but those two ICIRs come from **different evaluators**. The only locally-archived RankIC convention (`selected_signal_metrics.csv`) shows **both** streams with *negative* rank IC/ICIR (overlay −0.0083/−0.329; momentum −0.0105/−0.588). The +0.77 overlay ICIR is **not traceable to any archived CSV** (grep finds it only in the prose docs).
- **Impact on claim:** The prose itself says to read the overlay IC as "approximately unchanged" (L599–604), yet the table bolds a +10% ICIR improvement. You cannot simultaneously call it "approximately unchanged / cross-convention" and bold it as the overlay's win. A PM will read this as a manufactured rank-side edge.
- **Fix:** Recompute the overlay RankIC/ICIR under the **same canonical evaluator** as the momentum baseline and show traceable numbers; or drop the bold and print "≈ momentum (cross-convention, not separately traceable)." Also resolve the sign-flip so one canonical evaluator runs end-to-end.

### P1-B — The visually strongest 30d row (LightGBM Sharpe 1.23) **fails the paper's own selection rule** and is exempted from DSR/PBO
*Files:* `tab:route_b_30d` and `tab:results` 30d block (L764–766); `docs/horizon_comparison.md` L67.

- That LightGBM 30d sector row (RankIC 0.0362, Sharpe 1.226, ret 12.95%) has **validation ICIR = 0.0804** and val Sharpe 0.16. Under the stated protocol ("best model by across-fold mean validation rank ICIR"), it would **not be selected** at 30d (MLP wins, val ICIR 0.49). It is also the only 30d row exempt from DSR/PBO ("artifacts not archived," L564–566).
- **Impact on claim:** The most attractive number in two tables is an unaudited, validation-failing test-set artifact — the exact overfitting pattern the paper warns against. It anchors the reader on a 1.23 Sharpe the paper's own discipline rejects.
- **Fix:** Annotate it as failing validation selection (val ICIR ≈0.08) and either archive its per-period stream and charge it DSR/PBO, or demote it to prose. Do not leave it as the visually-best 30d line.

### P2-C — Missing **incremental (paired) significance test** — I computed it; it reframes the result
*Files:* Results/Discussion; computed from `output/.../baseline_score_test_backtest.csv` + `output/alpha_robustness_audit_route_b_30d/residual_overlay_test_backtest.csv` (35 paired periods).

The paper judges "overlay > momentum?" only via **absolute** point estimates (0.74→0.99 Sharpe, −13.8%→−7.3% DD) plus absolute DSR/bootstrap/PBO on the overlay alone. It never tests the **increment**. From the archived per-period streams:

| Incremental test (overlay − momentum, N=35) | Result |
|---|---|
| Mean per-period return diff | +0.06% (≈+0.5%/yr) |
| **Paired t-stat on return diff** | **0.25** (not significant) |
| corr(overlay, momentum) | **0.93** |
| Sharpe gap point / **paired bootstrap 95% CI** | +0.25 / **[−0.18, +0.63]**, P(gap>0)=0.88 |
| Per-period sd: momentum → overlay | 0.0357 → **0.0285** |

- **Impact on claim:** The overlay adds **no statistically distinguishable return** (t=0.25); the *entire* Sharpe/drawdown gain is **volatility reduction**. This is the cleanest, most decisive statement of the paper's own thesis and it is absent. It also exposes that "improves Sharpe and drawdown" overstates what happened.
- **Fix:** Add this paired test (minutes, already-archived data) and **reframe the overlay as a volatility/drawdown-dampening overlay on momentum, not candidate residual alpha.** This *reinforces* the conservative conclusion.

---

## Focused experiments / calculations (highest ROI first, all ≤ a few hours)

1. **Paired increment test (P2-C)** — drop into Results + Table `tab:route_b_30d` as a Δ-row; reframe Discussion (L868–878). Minutes.
2. **Hold-out-specific survivorship bound.** Delistings cluster in 2008/2020 (in train/val), while the 2022–2026 *hold-out* had very few S&P 500 delistings — so bound survivorship impact on the *specific* headline claims (likely small) instead of only a uniform 2%/yr haircut. Conversely state that the uniform haircut *understates* crisis-clustered short-leg damage for any full-history claim. Sharpens the honest reading of `survivorship_haircut.csv`.
3. **Block/stationary bootstrap** for the absolute Sharpe CI (current `[0.019,1.796]` looks i.i.d. over 35 autocorrelated periods) — and report the *paired* version too.
4. **DSR trial-dispersion sanity check.** `multiple_testing_dsr.csv` uses `trial_sharpe_std=0.4695` across 884 heterogeneous trials (mixed horizons/targets → different per-obs Sharpe scales). Confirm per-observation Sharpe normalization is horizon-consistent so the expected-max-null (1.512) isn't inflated by horizon heterogeneity. (Cuts toward conservatism — robustness note, not a correctness bug.)
5. **Symmetry fix:** archive the LightGBM 30d per-period stream and charge it the same DSR/PBO (P1-B), so the table is internally consistent.

---

## Wording / table / figure changes for the final report

- **Headline (L66–72) & Conclusion (L892–895):** change "improves … point-estimate Sharpe and drawdown" → "**reduces volatility and drawdown without adding statistically distinguishable return (paired t≈0.25); the overlay is 93% correlated with momentum.**"
- **`tab:route_b_30d`:** unbold/recast the overlay ICIR (P1-A); add the paired-increment row; annotate LightGBM val ICIR ≈0.08 and λ=0.3 as *not validation-selected*.
- **`tab:results`:** the 5d/30d blocks are sector-relative but the 20d block is **market-relative** (L760–762), where momentum looks best (RankIC 0.042, Sharpe 0.82). It's disclosed (caption), but mixing target families across horizon rows reads as horizon×family cherry-picking — standardize to sector-relative or add an explicit per-row family flag + one-line justification.
- **Factor attribution (L812–821):** be explicit that neutralization *raises* Sharpe (0.987→1.006) while halving return (8.27%→5.17%) and raising turnover (0.49→0.70); the demotion rests on **FM t=0.05 and negligible RankIC**, not a Sharpe drop. As written it's a touch hand-wavy.
- Honesty framing of failed methods (graph/GAT/MLP/Kronos/seed-bag/Kaggle-agg) is **good** — placebo-beats-real graph result (L628–644), MLP demotion, and Kronos-as-future-data-route (L837–843) are all appropriately demoted. Keep as-is.

---

## Residual risks (no blockers)
- **Survivorship is bounded, not corrected** (no PIT constituents/delisting returns) — inherent data limit, acknowledged; momentum is precisely the signal it most flatters, so the haircut should be read as a floor, not a fair estimate.
- **N=35 → very low power**; every 30d conclusion is fragile. The paired test (P2-C) makes this explicit rather than implicit.
- **Cross-evaluator RankIC sign flips** (positive canonical vs negative audit convention) reconcile on economics but are a reproducibility smell — a single canonical evaluator end-to-end would remove the largest remaining audit ambiguity.
- Page budget is fine: the PDF is **9 pages** (the improvement plan's >10-page concern is resolved).

**Process note:** This review ran as the read-only Copilot-Opus paper reviewer per `AGENTS.md`/`docs/copilot_opus_reviewer_mcp.md`. No files were edited; findings only. The MCP `manual_review` tool was not invoked (not exposed in this runtime) — this is the direct paper-first review; save it under `review-stage/` per the gate.
