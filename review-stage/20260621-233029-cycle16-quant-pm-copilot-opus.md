I'll review this as a read-only quant research reviewer. Let me start by mapping the repository and reading the key files.

Let me read the paper in sections and explore the directory structure in parallel.

Let me continue reading the paper and key docs in parallel.

Let me continue reading the paper's results and discussion sections, plus the Route B doc.

Let me read the rest of the paper (results tables, discussion, conclusion) and the triage/improvement docs.

Let me read the final paper sections (results table, discussion, conclusion) and the improvement plan.

Let me read the paper's conclusion and verify key output artifacts against the claims.

The paper is unusually self-critical and thorough. Now I need to verify the headline numbers against the actual artifacts, and check the page limit. Let me inspect the artifacts and outputs.

Let me verify the page count and cross-check headline numbers against artifacts.

PDF is exactly 10 pages (limit resolved). Momentum baseline numbers match. Now let me verify the Route B audit, paired-increment, IC, and PIT artifacts.

Let me read the core verification artifacts to confirm the paper's headline statistics.

Numbers verify cleanly so far. Let me confirm the Route B DSR/PBO/Fama-MacBeth/capacity figures and check the factor-sleeve book performance.

Numbers verify cleanly across all artifacts. Let me check figures exist, LaTeX has no broken references, and scan for any undefined refs.

All figures present, clean compile (10pp, zero overfull boxes, no undefined refs). Let me do final due-diligence on the PIT/survivorship setup and the leakage review before writing up.

I've reviewed the paper, all 13 verification artifact bundles, the robustness audit, the leakage review, and confirmed a clean 10-page compile. Every headline number traces to an artifact. Here is my review.

---

## Reviewer verdict

**No P0 paper-level blockers.** This is a rigorous, unusually honest study. I independently reconciled every headline statistic against the artifacts and they match: momentum 5d/30d (0.627/0.740 Sharpe, IC 0.0234/0.0282), traded-horizon block-boot IC t = 2.41/2.13/1.89/1.85 with the 20d/30d CIs crossing zero, daily IC t = 3.54 / NW-21 t = 4.39, paired increment t = 0.25 / corr 0.93, full-grid DSR 0.003 (N=884) vs same-target 0.814, PBO 0.50, FM t = 0.05, capacity, borrow, survivorship, and regime slices. Compile is clean (10pp exactly, all 6 figures present, zero overfull boxes, no undefined refs). Leakage controls (purge/embargo/execution-lag/overlap) are documented and sound. The paper **under-claims** rather than over-claims — the remaining issues are positioning, not correctness.

---

## Blocker findings

### P1 — Evidence hierarchy is scattered; the endorsed benchmark's *portfolio* case is weak and not assembled honestly in one place
- **Where:** Abstract (L70–106), §Results "decisive test" (L510–521), §Discussion regime/PIT (L902–931, L963–977), Table `tab:results`.
- **Impact on claim:** The book you endorse ("the 5-day sector-neutral implementation … is the benchmark I would keep") rests, on the *portfolio* axis, on the single most fragile evidence in the paper: 5d momentum net Sharpe is **negative in 2 of 4 regimes** (−0.95 GFC, −0.14 2017–21), mean-return **t = 1.31** (CI [−0.32, 1.63] crosses zero), and the one defensible survivorship correction (inclusion-side PIT) cuts it **0.62 → 0.46 with CI [−0.49, 1.43]**, again crossing zero — and the hold-out is itself the best regime. The disclosures all exist but are spread across three sections, so a PM cannot see that the *portfolio Sharpe is not fundable as shown* and that only the **IC** survives (1d OOS CI [0.0115, 0.0297] excludes zero; discovery block-boot t = 2.42 also excludes zero).
- **Fix:** Add a single 5-row "evidence ladder" table for the momentum benchmark — IC (strong, multi-regime) → traded-5d block-boot IC (t=2.41) → portfolio Sharpe (directional) → PIT-filtered (crosses zero) → borrow-adjusted — and state in the abstract that the portfolio Sharpe is *corroborating/directional only* and the **IC is the evidence base**. Promote the regime-slice Sharpe table out of §Discussion prose (L963–977) into a real table; it is the most decision-relevant robustness result and is currently buried.

### P1 — The positive deliverable / conviction is too diluted for a PM pitch
- **Where:** Abstract, §Limitations and Conclusion (L995–1036).
- **Impact:** Every positive statement is immediately self-negated, so the net read is "nothing is tradable" — exactly the B-/C+ failure mode `docs/report_improvement_plan.md` §0/§8 set out to fix. The rigor is A-grade; the *research-taste payoff* is under-stated.
- **Fix:** Add one crisp decision paragraph (plan §8, Route A): *what* you would trade (low-turnover 5d cross-sectional momentum), *expected realistic net* after the haircuts you already computed, the explicit conditions that would make you trade the Route B sleeve (pass CPCV + style-neutral FM), and *where the next research dollar goes* (PIT universe + delisting returns). The components exist; state them as a decision, not as scattered caveats.

---

## Non-blocking issues

### P2 — "Untouched hold-out" language vs horizon selection
The 30d horizon was chosen *after* seeing that 5d/10d "did not deliver reliable net economics after costs" (L256–259, "selection step, not an exogenous design fact"). The full-grid DSR (884 trials) is the correct charge and is applied — but the repeated phrase "untouched hold-out" (L510, L778) overstates purity. **Fix:** call it a "single-evaluation hold-out (used once per config; horizon framing was informed by hold-out economics and is charged in the full-grid DSR)."

### P2 — Same-horizon Sharpe differs across scripts
20d momentum 0.822 (`momentum_portfolio_uncertainty`) vs 0.828 (PIT current-membership) is footnoted in `tab:results`, but 30d **regime-slice post-2022 Sharpe 0.672 vs canonical 0.740** (~9%, 37 vs 35 rebalance periods) is not reconciled. **Fix:** one footnote noting the different rebalance grid.

### P2 — `tab:results` visual trap
The **largest** hold-out Sharpe (1.23) and RankIC (0.036) in the entire paper is the LightGBM-30d row — correctly demoted ("val ICIR 0.08, unaudited") but it sits in the table with the biggest numbers. **Fix:** gray it / append "(rejected by validation)" inline so a skimmer can't misread it as a positive ML result.

### P2 — Artifact hygiene (reproducibility, not paper text)
In `pit_inclusion_sensitivity/pit_inclusion_summary.csv` the `route_b_overlay` IC column is on the **residualized-eval** label (−0.0083) while the `momentum` IC column is on the **raw** label (+0.028) — apples-to-oranges in one table. The paper only cites Sharpe from this file, so no paper error, but make the column convention-consistent for auditability.

---

## Highest-ROI experiments (few hours, existing data only)

1. **CPCV / combinatorial-purged Sharpe *distribution* for 5d momentum (and the overlay).** The plan asked for this (P1-3) but only calendar slices shipped. A purged-combinatorial Sharpe distribution is the single most direct answer to "is the benchmark single-regime luck?" — the biggest open question. Computable on the current panel.
2. **Delisting-*side* survivorship bound.** Inclusion-side PIT is admittedly optimistic-direction-only. A parametric phantom-short-loser injection (hazard × delisting return on the short leg) converts "direction is adverse" into a *number* and closes plan §1 "矛盾 A." You already have the haircut machinery.
3. **One "all-in" net Sharpe for the endorsed book** = cost + borrow + inclusion-PIT + delisting-haircut stacked, so the abstract quotes a single realistic figure instead of the gross-of-everything 0.62.
4. **IC half-life / decay curve for momentum** — cheap; yields a clean, falsifiable execution-horizon recommendation.

---

## Wording / table / figure changes for the final report

- Abstract: lead with the IC evidence ladder; explicitly mark portfolio Sharpe "directional, single-regime, not fundable as shown."
- Add the momentum **evidence-ladder** summary table; promote the **regime-slice Sharpe** prose into a table.
- Add the **one-paragraph trade decision** (conviction).
- Replace "untouched hold-out" → single-evaluation language; reconcile the 30d 0.672 vs 0.740 footnote; mark the LightGBM-30d row validation-rejected.

**Residual risks (acknowledged, not fixable in-dataset):** no PIT constituents or delisting returns (survivorship is bounded, not corrected); no market-cap/fundamentals, so "factor-neutral" is price/volume+sector only — both are correctly disclosed and belong in Limitations, not treated as solved.

**Copilot Opus reviewer gate:** this read-only paper review ran and completed; no files were edited, no commands beyond read-only inspection. Outcome: **no P0 blockers, two P1 positioning items, four P2 polish items.** Recommend addressing the two P1s (evidence ladder + conviction paragraph) and ideally experiment #1 (CPCV) before submission.

