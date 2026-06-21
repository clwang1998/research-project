I'll review this as a read-only quant PM reviewer. Let me start by exploring the repository structure and reading the key files.

Let me explore the directory structure and read the primary deliverable files.

The main deliverable is the LaTeX report. Let me read it along with the latest scope file and key docs.

Let me read the main report in full. It's 896 lines, so I'll read it in sections.

Continuing through the report's results and discussion sections.

I have the full report. Now let me cross-check the key claims against the supporting docs and output artifacts.

Tables trace cleanly to `horizon_comparison.md` and the Route B doc. Now let me verify the output artifacts and read the remaining planning/triage docs to check the audit pipeline traceability.

The plan and triage docs confirm the intended narrative. Now let me verify the actual output artifacts — especially whether the Route B overlay's economics and the DSR/PBO audit come from a consistent return stream.

Let me examine the audit summary and the key statistical files to validate the DSR/PBO and N counts.

The audit return streams match the reported economics for both baseline and overlay. Let me verify the remaining momentum baseline rows (5d sector, 20d market) and check the figures referenced in the report.

All momentum rows verify exactly. Let me check the compiled PDF page count (the improvement plan flagged a 10-page limit) and confirm the log compiled cleanly.

PDF is 9 pages (under the 10-page limit) and compiles cleanly. Let me verify the featured frequency-scan and sleeve-book numbers have backing artifacts, since those appear prominently in Results.

I've completed my review. All headline tables trace cleanly to committed artifacts; the PDF is 9 pages and compiles cleanly. Here are my findings as a read-only quant PM reviewer.

---

# Copilot Opus — Quant PM / Senior Researcher Review
**Verdict: No P0 paper-level blockers. Submittable as an honest triage / negative-result study.** The methodology hygiene is genuinely above bar (leakage controls, overlap correction, DSR/PBO, honest demotion of graph/GAT/MLP/Kronos). Every headline number I checked is traceable and accurate. The remaining issues are **framing/emphasis (P1)** and **traceability/presentation (P2)** — they affect how the central claim reads, not its correctness.

## Verification performed (all pass)
- Table `tab:results` rows trace exactly to `output/momentum_baseline_priority/*.json` and `docs/horizon_comparison.md` (5d sector Sharpe 0.627, 20d market 0.822, 30d LightGBM 1.226, etc.).
- Table `tab:route_b_30d` and `tab:p0audit` trace exactly to `output/alpha_robustness_audit_route_b_30d/` (overlay test Sharpe 0.9865; DSR full-grid 0.003 over 884 trials, same-target 0.814 over 14; PBO 0.50; FM t=0.048; N=35 non-overlapping periods; bootstrap CI [0.019,1.796]).
- PDF = 9 pages (under the 10-page cap the plan flagged); compiles with no undefined refs/overfull warnings.

---

## P1 — Should fix before submission (framing distorts the claim)

**P1-1. The headline leads with a point estimate that every statistical test says is insignificant.**
- *Where:* §1 "Headline design" (the "Sharpe 0.740→0.987, drawdown −13.8%→−7.3%" framing), §Results "Route B 30-day residual overlay," and the Conclusion ("improves the momentum book's hold-out Sharpe from 0.740 to 0.987 and drawdown").
- *Impact:* The same overlay has full-grid DSR 0.003, PBO 50%, Fama–MacBeth marginal t=0.05, and an IC delta of +0.002. Under the audit's own convention the standalone residual model scores only Sharpe 0.318 (turnover 0.76); the +0.25 Sharpe / halved-drawdown jump from a λ=0.2 sleeve over **35 periods** is precisely the fragile interaction DSR/PBO exists to reject. A PM skimming the headline sees "+33% Sharpe, half the drawdown"; the actual finding is "nothing beats momentum at a meaningful confidence level." Everything is *disclosed*, but the emphasis over-promotes a null result.
- *Fix:* Reframe the headline finding as the negative result ("on this dataset no multivariate/graph/residual construction produces statistically deflated alpha; 12–1 momentum is the only robust signal"), and demote the overlay to "a point-estimate improvement that does **not** survive deflation (DSR 0.003, PBO 50%, FM t=0.05)." Lead with the verdict, not the 0.99.

**P1-2. Asymmetric audit: the strategies that look best are exempted from the harshest test.**
- *Where:* Table `tab:results` 30d block bolds plain LightGBM Net Sharpe **1.23** (and `horizon_comparison.md` shows plain XGBoost 1.21, Ridge 1.17) — all above the overlay's 0.99 and momentum's 0.74. The text exempts them from DSR/PBO because "their per-period artifacts are not archived with the Route B audit" (lines 560–562).
- *Impact:* The one strategy charged the full 884-trial deflation (the overlay) is held to a higher bar than the three plain models that actually post higher Sharpe. This is selective rigor, and it invites the obvious PM question: "if plain 30d LightGBM is 1.23, why is your lead a 0.99 overlay?" The honest answer (turnover 0.49 vs 0.63 + residual-sleeve economic role) is much weaker than a 0.24-Sharpe gap.
- *Fix:* Either (a) archive the plain 30d model artifacts and run the same DSR/PBO/CSCV on them, or (b) un-bold their Sharpe and state explicitly that all 30d Sharpes (0.74 / 0.99 / 1.17 / 1.23) are statistically indistinguishable over N=35 — the 30d block is too thin to rank.

**P1-3. The robustness "ladder" is one thin sample re-used, not independent confirmation.**
- *Where:* §Results `tab:p0audit` (capacity, survivorship haircut, factor-neutral Sharpe) and §Discussion.
- *Impact:* Capacity (0.948/0.864), survivorship haircut (0.837), and factor-neutral Sharpe (1.006) are all transforms of the **same 35-period overlay return stream and the same selected strategy**. They read as a stack of independent stress tests but share one noisy sample; none is an out-of-sample confirmation.
- *Fix:* Add one sentence stating these checks share the N=35 stream and the selected configuration, so they bound sensitivity but do not add independent statistical support.

---

## P2 — Worth addressing (traceability + presentation)

**P2-1. Two *featured* Results items have no committed numeric artifacts.** The frequency-confirm table (`tab:frequency_confirm`: mom t 3.54, amihud 5.48→0.40) and the sleeve-book diagnostic (DSR 0.056, Sharpe 0.675/−0.525/0.146, weights 43.3/56.7) are stated as precise numbers, but `output/signal_horizon_surface/` and `output/factor_sleeve_book/` **do not exist** — only the two PNGs in `report/figures/` were copied over. The generating scripts (`scripts/build_signal_horizon_ic_surface.py`, `build_factor_sleeve_book.py`) are deterministic, so it's regenerable, but this is the *same* traceability gap the paper congratulates itself on closing for Route B (§"Route B reproducibility"). *Fix:* run both scripts and commit the CSVs (`native_horizon_summary_*.csv`, `book_performance.csv`, `dsr_combined.csv`).

**P2-2. `tab:p0audit` "Factor-neutral Sharpe 1.006" reads as "alpha survives neutralization."** At a glance the Sharpe even *rises*; the real story is in the adjacent FM t=0.05 plus return falling 8.27%→5.17% and turnover rising 0.49→0.70 (`factor_neutral_ic.csv` confirms). *Fix:* relabel the row "Factor-neutral Sharpe 1.006 (return 8.3%→5.2%, turnover 0.49→0.70, FM t=0.05)" so the row can't be read as evidence of orthogonal alpha.

**P2-3. Audit-pipeline IC sign disagrees with the headline evaluator.** Momentum's Rank IC is +0.0282 (canonical JSON) but −0.0105 under the audit convention; the overlay is −0.0083 (`selected_signal_metrics.csv`). The economic rows match across both evaluators (good), but a reproducibility-first paper shouldn't ship a DSR/PBO pipeline whose IC column has the wrong sign on the benchmark. The report discloses this (lines 586–600) — acceptable, but fix the convention or add a one-line note that only the IC label, not the return stream, is affected.

**P2-4. 30d horizon was chosen because shorter horizons "did not deliver reliable net economics" (lines 230–232).** That is itself a selection step that inflates the multiple-testing burden (and helps explain DSR→0.003). State it explicitly as a selection caveat rather than a neutral design choice.

**P2-5. Moving-benchmark Sharpe.** Momentum's Sharpe appears as 0.627 / 0.675 / 0.740 / 0.746 / 0.822 across conventions/horizons. All disclosed, but the central benchmark should have one canonical per-horizon number; the paper already lists "one canonical evaluator" as a limitation — make the convention explicit at each table.

---

## Highest-ROI experiments (a few hours, current data only)
1. **DSR/PBO the plain 30d LightGBM/XGBoost/Ridge** with the existing audit script (closes P1-2; likely shows they fail equally, which *strengthens* the negative thesis).
2. **Decompose the overlay drawdown improvement by year/regime** — confirm (as suspected) that −13.8%→−7.3% is one 2022 window; report the per-regime contribution. Directly de-risks P1-1.
3. **Quantify survivorship sign on momentum itself**, not just the overlay short side: the paper's one robust signal is the most survivorship-exposed. A simple `date_added` point-in-time inclusion filter on the momentum baseline would bound how much of the 0.74 Sharpe is current-constituent flattering.
4. **Re-run and commit the frequency-surface and sleeve-book CSVs** (closes P2-1).

## Wording / table / figure changes
- Rewrite the §1 headline and the Conclusion's first sentence to lead with the **negative** finding; move "0.740→0.987" into a hedged secondary clause already carrying DSR 0.003 / PBO 50% / FM t=0.05.
- `tab:results`: un-bold plain 30d LightGBM Sharpe/return, or add a footnote that 30d Sharpes are within noise (N=35); the bold currently reads as a winner the paper then disowns.
- `tab:p0audit`: relabel the factor-neutral row (P2-2).
- Add N and an error bar to every 30d Sharpe in `tab:route_b_30d`/`tab:results` (the CI is wide; show it inline).

## Residual risks (no P0, but flag in Limitations)
- Entire 30d story rests on **N=35 non-overlapping periods ≈ one momentum-friendly regime (2022–2026)**; differences among 0.74/0.99/1.17/1.23 are not separable.
- Survivorship is bounded by parametric haircut only; the headline "momentum is robust" claim is itself survivorship-sensitive and uncorrected.
- No size/value/quality factors exist in the data, so "factor-neutral" = price/volume+sector-neutral only — correctly scoped, but the paper cannot claim Barra/FF-style orthogonality.

**Bottom line:** credible, unusually honest, and submittable. Fix P1-1/P1-2 (reframe the headline to the negative result; stop letting un-audited plain models or an insignificant overlay read as wins) and it reads like a senior-researcher triage artifact rather than a model demo.

