I'll start by exploring the repository structure and reading the key files in parallel.

The report is large. Let me read it in sections and explore the directory structure in parallel.

Let me continue reading the report and key docs in parallel.

Good, the narrative is deflation-first and honest. Let me continue reading the report and the audit docs in parallel.

Let me continue reading the report results/discussion sections and the triage docs.

Let me read the rest of the report (discussion/conclusion) and the report improvement plan.

Let me read the report conclusion and verify the key numbers against the output artifacts.

Now let me verify the key reported numbers against the actual output artifacts.

Numbers match. Let me verify the Route B audit artifacts and the paired-increment / DSR claims.

Let me verify the paired-increment, momentum bootstrap, factor-neutral, and capacity numbers.

All Route B numbers reproduce exactly. Let me check the PDF page count, figures, and the reviewer protocol doc.

Let me determine the PDF page count (the improvement plan flagged the 10-page limit as a hard constraint).

PDF is exactly 10 pages (meets the limit) and all figures exist. Let me verify the model-comparison rows (Table 6) and the plain-LightGBM 30d claim against their sources.

Model-comparison rows all reconcile with `horizon_comparison.md`. Let me verify the 20d market momentum row and the momentum daily-IC t=3.54 source.

I've verified the report against its artifacts. All headline numbers reproduce exactly (momentum baselines, Route B overlay, DSR/PBO `0.003`/`50%`, paired increment `t=0.25`/`corr 0.93`, momentum bootstrap `t=1.51`/CI `[-0.22,1.85]`, capacity, survivorship, and every model row in Tables 6–7 vs `horizon_comparison.md`). PDF is exactly 10 pages; all figures exist. Here is my reviewer assessment.

---

## Verdict
**No P0 blockers.** The paper is submission-credible as an honest, deflation-first triage study. The headline is negative and disciplined, the benchmark is defensible, failed methods (graph/GAT/Kronos/MLP/seed-bag/Kaggle-aggregates) are honestly demoted, and the key statistics are reproducible from local artifacts. The risks below are credibility-polish, not claim-invalidating.

## P1 — should fix before final submission

**P1-1. The headline overlay's Rank IC is reported under a different evaluator than its own audit, which disagrees on sign.**
- Where: §Results Table 7 (`tab:route_b_30d`) and Table 6 (`tab:results`) show the overlay IC as "`≈0.028 / ≈0.77`"; §Results "Route B artifact check" admits the audit CSV gives overlay IC `-0.0083` vs baseline `-0.0105`. `selected_signal_metrics.csv` confirms negative ICs for both.
- Impact: the one headline row a PM scrutinizes carries an IC that cannot be reproduced under a single evaluator, and the two evaluators flip the sign. The *conclusion* ("IC gain negligible") is conservative and survives either way, but a sign-flipping convention invites distrust of every IC number in the paper.
- Fix: recompute the overlay Rank IC/ICIR with the **same** canonical evaluator (`eval_momentum_baseline.py`) used for the momentum row; replace the "`≈`" entries with exact single-convention values. Cheap, high-value.

**P1-2. The positive recommendation is load-bearing on momentum's daily IC `t=3.54`, which is not defended against signal autocorrelation or the 12-factor pre-registered search.**
- Where: §1 headline, §Results "Signal-frequency diagnostic," Table 5 (`tab:frequency_confirm`); source `native_horizon_summary_excess_sector.csv`. The conviction call ("keep 12-1 momentum as the core benchmark") rests on this `t` plus literature — while momentum's *own* hold-out portfolio Sharpe is insignificant (`t=1.51`, CI `[-0.22,1.85]`).
- Impact: the entire "what I'd actually trade" story hinges on a single t-stat. It's a 1-day-horizon (non-overlapping) IC so it is *not* overlap-inflated, but `mom_252d_skip_21d` is highly persistent and the t-stat is not reported with a Newey–West/block-bootstrap SE or a multiple-testing charge across the 12 pre-registered factors.
- Fix: add a block-bootstrap or Newey–West t-stat for the momentum daily IC, and state momentum is literature-pre-specified (so exempt from the 12-factor DSR charge). One sentence + one number closes the gap.

## Focused experiments (each a few hours, data-only, no new data)
1. **Single-evaluator overlay IC** (fixes P1-1): rerun the overlay score through the canonical evaluator; report exact IC/ICIR.
2. **Robust momentum-IC inference** (fixes P1-2): block-bootstrap / Newey–West t on the daily momentum IC series.
3. **Momentum per-year hold-out Sharpe** (2022/23/24/25): the paper asserts regime variability but never shows the *recommended* signal's stability; a 4-bar panel directly supports the conviction call.
4. **Long-vs-short leg attribution + leg-specific survivorship haircut**: survivorship contaminates mainly the short leg; show leg PnL split so the haircut (currently a symmetric scalar) is anchored to the actually-exposed short book. The stress case only knocks Sharpe `0.99→0.84`, which reads mild for a current-membership universe — leg attribution would make it credible.

## Wording / table / figure changes
- **Tables 6 & 7:** replace "`≈0.028 / ≈0.77`" with exact single-convention IC/ICIR (per P1-1).
- **Table 5 (`tab:frequency_confirm`):** reconcile with the archived CSV — momentum Disc `t` `2.20→2.23`, Disc ICIR `0.589→0.595`; reversal Test `t` `-0.91→-0.94`; volume Test `t` `-1.91→-1.93`. Sub-0.05 but breaks exact traceability.
- **Table 7 "Plain LightGBM" row (Sharpe 1.226):** it visually dominates the headline overlay. The text correctly demotes it (val ICIR `0.08`, below null), but consider greying/relocating it below the overlay so the ordering can't be read as cherry-picking.
- **Annualization convention:** `route_b_paired_increment/paired_increment_summary.csv` reports momentum/overlay annual return geometrically (`7.48%`/`8.22%`) while the report and `selected_signal_metrics.csv` use arithmetic (`7.78%`/`8.27%`) for the *same* stream (identical Sharpe). Standardize one convention across artifacts so "7.78% vs 7.48%" doesn't surface under scrutiny.
- **§1/§Conclusion framing:** state plainly that the positive call is **IC- and literature-anchored, not portfolio-significant in this sample** (momentum book `t=1.51`), so the conviction language doesn't read as out-running the in-sample evidence.

## Residual risks (disclosed, acceptable, but worth a reviewer flag)
- **Single hold-out regime (2022–2026, momentum-friendly).** Disclosed; CPCV/per-year slices would harden it (experiment 3).
- **N=35 monoculture:** capacity, survivorship, factor-neutral, and paired-increment tables are all transforms of the *same* 35-period overlay stream. The paper says so (§Results PM-audit), but the audit tables should not be read as independent confirmation — keep that caveat prominent.
- **OHLCV-only factor neutralization** cannot reach Barra/Fama–French (no market cap / fundamentals). Correctly scoped, but the "factor-neutral" label should keep its "price-volume + sector only" qualifier wherever it appears.
- **Survivorship remains uncorrected** (current-membership-on-history); the haircut is a sensitivity, not a fix — already stated, keep it that way.

Net: this reads like a credible senior-researcher triage artifact, not a code demo. Fix P1-1 (single-evaluator IC) and P1-2 (robust momentum-IC t-stat) and it clears the bar for submission.

*(Read-only review: no files edited, no commands beyond inspection, nothing committed.)*
