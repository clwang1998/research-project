I'll start by surveying the repository structure and reading the key paper and documentation files in parallel.

Let me read the paper in sections and explore the key directories in parallel.

Continuing to read the paper and key docs in parallel.

The paper is rigorous and self-critical. Let me continue reading the paper body and the audit docs in parallel.

Let me read the results and discussion sections of the paper, plus the experiment triage and report improvement plan.

Let me read the rest of the paper (discussion, conclusion) and the remaining docs.

Let me read the final sections (discussion/conclusion) and check the reviewer MCP doc plus the PDF.

Let me read the conclusion's end and verify the page count (the 10-page limit is a stated hard constraint).

The paper is exactly 10 pages — the page-limit concern is resolved. Now let me verify the headline numbers against the underlying artifacts. Let me inspect the artifacts and key output summaries.

Let me verify the key headline numbers against the actual JSON artifacts.

All headline numbers verify exactly. Let me check the paired increment, DSR/PBO audit, and PIT sensitivity artifacts.

Excellent — every number verifies exactly against artifacts. Let me complete verification on PIT sensitivity, portfolio uncertainty, and borrow, then check the figures referenced.

Let me verify the PIT summary and portfolio uncertainty t-stats/CIs (the headline significance claims).

All headline numbers trace to artifacts and match exactly — this is exceptional reproducibility. Let me confirm the figures exist and skim the README for the intended deliverable framing.

Let me be precise before finalizing — checking whether any multi-regime/CPCV Sharpe distribution exists for the headline book, and confirming the portfolio-uncertainty CIs.

I've completed a thorough read-only review: I read the full paper (`report/sp500_case_study.tex`, 10 pages confirmed), the Route B / P0 audit / triage / improvement-plan docs, and verified every headline number against the underlying artifacts in `output/` and `report/artifacts/`. **Every number I checked reproduces exactly.** Findings below.

---

## Verdict

**No P0 blockers.** Methodology hygiene (leakage controls, overlap correction, walk-forward, non-overlap ICIR, DSR/PBO, PIT and borrow sensitivities) is genuinely top-decile for a take-home, the page limit (10pp) is met, failed methods (GAT/Kronos/MLP/seed-bag/Kaggle-agg) are honestly demoted, and the headline numbers trace cleanly to artifacts. The remaining issues are **P1/P2 framing problems plus one real experimental gap**, not integrity problems.

---

## Blocker findings (priority order)

**P1 — The headline "tradable book" is sold on a portfolio Sharpe that is not statistically distinguishable from zero.**
- Where: Abstract (§1, "the specific book I would keep… is the 5-day sector-neutral implementation… net Sharpe 0.62–0.63"); Conclusion (§7, "most statistically reliable tradable benchmark").
- Issue: Verified in `momentum_portfolio_uncertainty` / `pit_inclusion_sensitivity_5d`: 5d mean-return *t*=1.30, bootstrap Sharpe CI **[-0.32, 1.62]** (crosses zero), and PIT-inclusion cuts it to 0.46 with CI **[-0.49, 1.43]**. So the *portfolio* a PM would actually fund has a Sharpe indistinguishable from zero in-sample. The paper *does* disclose this and correctly pivots to IC (block-bootstrap *t*=2.41; daily *t*=3.54 / NW-21 *t*=4.39) as the real evidence — but the lead sentence still invites a PM to read a tradable 0.63-Sharpe product.
- Impact: The single most important claim (what would you trade) is supported by IC, not by a significant portfolio Sharpe.
- Fix: Reword the headline to "a statistically detectable, low-turnover momentum **signal** (IC *t*=2.4–4.4) whose standalone long–short **portfolio** Sharpe is positive but not significant at this sample size (CI crosses zero)." Lead with the IC evidence; present 0.62–0.63 as a point estimate with its CI attached.

**P1 — All headline economics come from a single, momentum-friendly regime (2022–2026); the promised multi-regime / CPCV Sharpe distribution is not in the paper.**
- Where: Results/Discussion (§5–6, Fig. `fig_fold_stability`); improvement-plan P1-3.
- Issue: `momentum_portfolio_uncertainty/run_summary.json` confirms `holdout_start=2022-01-01` for *every* Sharpe/CI. Fold stability (Fig. 6) is in **ICIR (signal space)**, and PBO/CSCV is an overfit probability — neither is a **Sharpe distribution across regimes** for the tradable book. 2008/2020 are mentioned but the headline book's Sharpe is never reported there.
- Impact: Economic conclusions are conditioned on one favorable regime; the paper says so verbally but doesn't quantify it. This is the biggest gap a PM will press.
- Fix: Report the 5d momentum book (and 30d overlay) Sharpe/IC across pre-2022 walk-forward OOS folds or CPCV blocks (2008–2011 / 2012–2016 / 2017–2021 / 2022–2026). The panel goes back to 2000/2008, so this is data-available and high-ROI.

**P2 — Headline horizon (5d) is itself a mild, uncharged multiple-comparison.**
- Where: Abstract/§5, `momentum_ic_traded_horizons`.
- Issue: Block-bootstrap IC *t* falls monotonically with horizon (2.41→2.13→1.89→1.85) and only 5d/10d have IC CIs excluding zero. 5d is chosen among {5,10,20,30}×{sector,market}. DSR is applied to the model grid (N=884) and the 12-factor scan, but not to this horizon/target selection. Largely mitigated by the pre-registered 1-day IC anchor and by 5d also being lowest-turnover and most PIT-robust.
- Fix: One sentence: conclusion is horizon-robust (all horizons positive IC); 5d chosen for turnover, not for maximal significance.

**P2 — Two slightly different Sharpes for the "same" momentum book (5d 0.627 vs 0.620; 20d 0.822 vs 0.828).**
- Where: Table 5 footnote vs Discussion/Abstract. Explained as canonical-vs-PIT-comparison universe filtering — internally consistent and honestly footnoted, but forces the reader to track two numbers per object.
- Fix: Pick one canonical evaluator for the headline; relegate the other to the PIT sensitivity table.

**P2 — Full-grid DSR=0.003 carries heavy rhetorical weight despite being acknowledged as "not a clean family-wise theorem."**
- Where: §6, Table 4. Pooling 884 heterogeneous trials into one cross-trial dispersion is a defensible *conservative* choice; the same-target DSR=0.814 is the cleaner number. Both are shown (good). Just ensure the "overlay fails" conclusion doesn't read as if 0.003 were exact.

---

## Focused experiments that would most improve the report (each ≤ a few hours, data-available)

1. **Multi-regime Sharpe distribution (highest ROI).** Re-run the 5d momentum book and 30d overlay over pre-2022 walk-forward/CPCV blocks; report a Sharpe distribution + 2008/2020 sub-period rows. Directly closes the P1 single-regime gap and converts "momentum-friendly window" skepticism into evidence.
2. **Deflate the traded-horizon IC selection.** Add a Bonferroni/DSR-style adjustment across the {horizon × target} IC grid so *t*=2.41 isn't read as a single pre-specified test. Cheap; removes the P2 selection critique.
3. **Long-history momentum IC by sub-period** (2008–2011 / 2012–2016 / 2017–2021 / 2022–2026). Shows the *signal* is regime-stable even where portfolio Sharpe is thin — strengthens the one claim the paper actually wants to defend.
4. **One reconciled canonical evaluator table** so 0.627/0.620 and 0.822/0.828 collapse to single numbers with PIT/borrow as deltas.

---

## Wording / table / figure changes for the final report

- **Abstract:** Lead with one crisp conviction sentence ("I would trade low-turnover 5d cross-sectional momentum at modest size; I would not deploy the ML/graph zoo; next research dollar → point-in-time universe"), *then* the caveats. The current abstract is so hedged it reads as "nothing works" — the improvement plan's own "self-falsifying narrative" risk (病灶 #8) is still partly present. Move dense parenthetical CIs into a table.
- **Table 5 footnote** is overloaded (PIT + borrow + CI reconciliation in one caption). Split into a small dedicated sensitivity table.
- **Add a "what I would trade and how much" callout box** — the conclusion has this in prose; surfacing it as a box gives the PM the decision in one glance.
- **State the 30d LightGBM exclusion rule at the table** (Table 3/5), not only later: it has the best raw Sharpe (1.23) *and* best Rank IC (0.0362) in the 30d block, so the validation-ICIR exclusion (0.0804 vs 0.4882) must be airtight at point of presentation, or a PM will ask "why is your best raw number the one you dropped?"

---

## Residual risks (acknowledged, not blocking)

- **Survivorship is a direction, not a correction.** PIT is inclusion-side only; deleted-name/delisting short-side exposure is unrecoverable from these files. The true survivorship-corrected Sharpe could be below the reported PIT haircut. The paper states this correctly.
- **Factor attribution is price/volume+sector only** (no size/value/quality) — correct given OHLCV-only scope, and honestly scoped, but it caps how strong any "residual alpha" claim can ever be.
- **Dividend adjustment uncertainty** on `close` — minor, disclosed.
- **DSR trial count (884) is a modeling choice**; the conclusion is robust to it only because the result is already weak.

Net: this is a credible, submission-ready *rigorous-triage* paper. To clear a senior-PM bar rather than a senior-auditor bar, fix the two P1 framing/evidence items (headline = signal-not-portfolio-Sharpe; add multi-regime Sharpe), and lead with conviction.

