I'll review this as a read-only quant PM reviewer. Let me start by exploring the repository structure and reading the key files.

Let me explore the directory structures and read the main report.

There's an active cycle19 scope file and many prior review rounds. Let me read the main report and the current scope/prompt.

Now let me read the main report (the deliverable) in full, along with the key supporting docs.

The report is notably self-critical already. Let me continue reading the report and the key audit docs.

Let me read the Results and Discussion sections of the report, plus the triage and improvement-plan docs.

Let me finish the report (Discussion/Conclusion) and read the improvement plan plus the most recent prior review cycle.

Let me read the final report sections and the most recent prior review to avoid duplicating findings.

I have the full report and the detailed cycle18 review. Now let me independently verify the headline numbers against artifacts and check the PDF page count — I won't just echo prior reviews.

Momentum baseline reconciles exactly. Let me verify the PDF page count via another method and check the traded-horizon IC and paired-increment artifacts (the load-bearing claims).

PDF is 10 pages (meets limit); traded-horizon IC reconciles exactly. Let me verify the paired increment, 1-day IC robustness, and DSR/PBO artifacts.

Numbers continue to reconcile. Let me verify the DSR/PBO, capacity, factor-neutral, and 1-day IC robustness artifacts.

Let me verify the 1-day IC holdout row (t=3.54, NW-21 t=4.39, CI [0.0115,0.0297]) — the most-cited stat.

All headline numbers reconcile exactly (1-day IC: t=3.54, NW-21 t=4.39, CI [0.0115,0.0297]). Let me check a few cross-horizon consistency points and whether prior wording fixes were applied.

Confirmed: 5d Sharpe 0.627, 20d 0.822 reconcile; "clearly survives" was removed; Route B exists **only at 30d**. Let me verify figures exist and scan for any broken refs or stale placeholders.

Verification complete. All 6 figures exist, no broken refs, no placeholders, PDF is 10 pages. Every headline number reconciles against the artifacts. Here is my independent review.

---

# Copilot Opus — Read-Only Quant PM / Senior Researcher Review
**Deliverable:** `report/sp500_case_study.tex` → `.pdf` (**10 pages**, meets ≤10).

## Reproducibility check (PASSED — I recomputed from artifacts, not prose)
I independently reconciled every headline number against the source files:
- Momentum 30d baseline `output/momentum_baseline_priority/...30d...json`: Sharpe **0.7403**, ann **7.78%**, DD **−13.83%**, turnover **0.401**, IC **0.0282** ✓
- 5d/20d momentum: Sharpe **0.627 / 0.822**, turnover **0.221 / 0.356** ✓
- Traded-horizon IC `momentum_ic_traded_horizons`: block-boot t **2.41/2.13/1.89/1.85**; **20d/30d CIs cross zero** ([−0.0013,0.063], [−0.0022,0.071]) ✓
- 1-day IC `momentum_ic_robustness`: plain t **3.54**, NW-21 t **4.39**, CI **[0.0115,0.0297]** ✓
- Paired increment: gap **0.246**, t **0.248**, corr **0.932**, boot gap CI **[−0.17,0.63]** ✓
- DSR **0.003** (N=884) / **0.814** (N=14); PBO **0.50**; FM t **0.048**; factor-neutral 8.27%→5.17% ✓
- Capacity $1B Sharpe **0.864**, p95 participation **25.3%**; survivorship base **0.951** / stress **0.837** ✓

**No fabricated or unreproducible headline number. No leakage, horizon-misalignment, or sample-boundary defect.**

---

## Blocker findings

### P0 — none
There is **no blocking paper-level integrity defect.** The paper does not claim ML beats momentum, frames Route B as drawdown-dampening (not alpha), and demotes graph/GAT/MLP/Kronos/seed-bag honestly. It under-claims if anything. Confirmed that cycle-18 fixes landed: "clearly survives" is **gone**, the 1-day stat is relabeled *signal existence*, capacity rows are labeled *extrapolated beyond calibration*, and arithmetic-vs-geometric return is reconciled in-text.

### P1-A — Horizon incoherence: the endorsed benchmark (5d) and the headline ML sleeve (30d) are different books *(NEW — not raised in prior rounds)*
- **Where:** §1 (l.67–69) endorses "the **5-day** sector-neutral implementation" as the benchmark. But Route B — the "best ML lead" — exists **only at 30d** (`output/route_b/...__target_excess_sector_fwd_30d`; no 5d run exists). Its advertised "+0.247 Sharpe" (Results l.591–624, `tab:route_b_30d`) is measured against the **30d** momentum book the paper explicitly declines to trade as the primary.
- **Impact on claim:** The two halves of the paper endorse different horizons. The overlay never touches the book you say you'd paper-trade, so "the overlay improves momentum" is true only for a horizon you didn't pick. A PM will immediately ask: *does the residual sleeve help the 5d book, or is the residual structure 30d-specific?* That question is currently unanswered, which undercuts the "one coherent story" goal of `report_improvement_plan.md`.
- **Fix:** Add one explicit sentence stating the residual sleeve is **30d-specific** and why (longer horizon → more residual structure / lower turnover), and stop phrasing it as improving "the benchmark." Best: compute the 5d Route B overlay; if it doesn't help, say so — that's a clean, honest result.

### P1-B — Self-defeating narrative persists *(carried over; still live)*
- **Where:** §Results/§Discussion. Structure improved (headline-first §1, evidence ladder), but nearly every positive result is still killed in the same sentence it appears.
- **Impact:** For a take-home, risks reading as "candidate found nothing" rather than "candidate has the judgment to know what's real." Conviction is the stated gap.
- **Fix (presentational):** Consolidate the repeated kill-shots into **one "Robustness verdict" box**; lead each result with the decision it drives; end §1 with one unhedged conviction sentence (what you'd paper-trade, sizing basis, the single experiment that flips the call).

### P2-A — Capacity curve holds turnover constant across AUM *(sharpens prior impact-extrapolation note)*
- **Where:** `capacity_curve.csv` / §Discussion l.990–994. `avg_turnover` is **identical (0.4941)** in every AUM row; Sharpe degrades only 0.97→0.86 to $1B. But at $1B, p95 participation is **25.3% of ADV** — 25× the 1%-ADV impact calibration. You physically cannot maintain 0.49 turnover at 25% ADV, so the near-flat curve understates degradation through **infeasible execution**, not just under-modeled impact.
- **Fix:** Report the AUM at which p95 participation hits ~10% ADV as the realistic ceiling, or re-run with a participation cap. Label $500M/$1B rows as already done, but add that turnover is held fixed.

### P2-B — The overlay fails DSR under *every* framing — say so once
- `multiple_testing_dsr.csv`: same-target DSR **0.814** (N=14) is called "encouraging," but **0.814 < 0.95**. So even the most favorable trial count does not clear conventional significance. **Fix:** one sentence — "the overlay does not reach 0.95 DSR under any trial-count assumption (0.003–0.814)," so the read is unambiguously *exploratory*, not "borderline pass."

### P2-C — Two residual hygiene items
- **Unlabeled stat:** l.620 "validation RankICIR **0.0804** vs MLP's **0.4882**" is on a different (walk-forward mean) scale than the 0.7–1.2 ICIRs elsewhere; already partially labeled, but a reader still can't reconcile it to any table. Tie it to a specific column.
- **Visual anchor:** the unaudited 30d LightGBM row (Sharpe 1.23 / 13.0%) is the single most attractive cell in `tab:results`/`tab:route_b_30d`; already grayed + "not a result," which is good — keep that tag prominent.

---

## Focused experiments that would most improve the report (each ≲ a few hours, current data only)

1. **Naive vol-timing negative control for Route B (highest ROI, NEW).** The entire Route B Sharpe gain (0.74→0.99) is a ~20% period-vol reduction (3.63%→2.89%) with a statistically indistinguishable return increment (t=0.25, corr 0.93). **Test whether a trivial non-ML rule — inverse-recent-vol scaling of the 30d momentum book — replicates the same Sharpe.** If it does, the residual XGBoost adds nothing beyond risk-scaling, and Route B should be demoted to "vol-targeting, no ML needed." This is the one negative control the otherwise-excellent control suite (random-graph, no-edge, reversal sleeve) is missing. Computable from `route_b_paired_increment/paired_returns.csv` + the momentum return stream.

2. **CPCV / combinatorial-purged Sharpe distribution for the no-fit 5d momentum book.** The paper concedes "calendar slices, not CPCV proof" (l.1013). Momentum requires no fitting → recompute on every purged path → converts the four regime point estimates (−0.95/0.33/−0.14/0.62) into a distribution and directly answers "single lucky regime."

3. **5d Route B overlay** (resolves P1-A): build the residual overlay on the endorsed 5d book and report whether it helps. One run; closes the horizon-incoherence gap definitively.

4. **Bootstrap CI on the canonical RankIC gap** (overlay − momentum, 0.0279 vs 0.0282). Turns "within evaluator noise" into a number; trivial from existing predictions.

*(Already done — do not re-request: cost break-even `route_b_cost_breakeven` gap≈0.25 to ~147 bps; borrow sensitivity; PIT inclusion.)*

## Wording / table / figure changes for the final report
- §1 + Conclusion: add **one unhedged conviction sentence**; state the 30d overlay is a **horizon-specific risk sleeve**, not an improvement on the endorsed 5d benchmark (P1-A).
- Add a single **"Robustness verdict"** box; strip per-paragraph re-hedging (P1-B).
- Capacity: note **turnover is held fixed across AUM** and give the ~10%-ADV ceiling (P2-A).
- Add one line that the overlay **fails 0.95 DSR under all trial counts** (P2-B); fix the 0.0804/0.4882 label (P2-C).

## Residual risks (acknowledged, not blocking)
- **N=35 non-overlapping periods** underlies every Route B economic claim — honestly disclosed, irreducibly thin.
- **Survivorship is inclusion-side only**; deletion side is parametric. Current "net sign indeterminate" framing (Discussion l.969–971) is correct — keep it.
- **DSR family size** remains a judgment call, not a theorem (paper says so).

---

**Bottom line:** **Submit-ready on integrity and reproducibility; not blocked by any P0.** Every number traces to an artifact. The remaining gaps are (1) a horizon mismatch between the endorsed 5d benchmark and the 30d ML sleeve (P1-A, new), (2) a still-self-defeating narrative (P1-B), and (3) a missing vol-timing negative control that could legitimately demote Route B further. Fixing P1-A and running experiment #1 (vol-timing control) + #2 (CPCV) would move this from "rigorous triage" to "credible, coherent PM-facing research."

**Reviewer-gate note:** I ran as the Copilot Opus read-only reviewer **directly** (MCP browser handoff not invoked). **No files edited; no commands beyond inspection run.** Outcome: **PASS with P1 framing/coherence fixes recommended, no P0 blockers.**
