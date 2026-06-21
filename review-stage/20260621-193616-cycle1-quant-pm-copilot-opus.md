I'll review this as a read-only quant PM/researcher reviewer. Let me start by exploring the repository structure and reading the key files.

Let me read the main report and key docs. First, let me check file sizes.

Now let me read the main report (the primary deliverable) in sections, plus the key audit docs.

This is rich. Let me continue reading the report and the key audit docs in parallel.

Let me continue reading the report results/discussion sections and the remaining key docs.

Let me read the rest of the report (results table, discussion, conclusion) and the report improvement plan.

Let me read the discussion/conclusion and check the reviewer MCP doc, then verify the numbers against actual output artifacts.

Now let me verify the headline numbers against the actual output artifacts, since I've spotted a potential momentum-Sharpe inconsistency between the main results table and the audit docs.

Let me check the canonical momentum baseline JSONs to verify the Sharpe numbers in the report's main results table.

This confirms a **major inconsistency**. The canonical momentum artifact says 5d sector momentum Sharpe = **0.627**, ann return **5.92%**, turnover **0.221** — but the report's main results table (Table `tab:results`) claims **1.05 / 13.5% / 0.16**. Let me verify how pervasive this is and check the Route B / audit artifacts.

Let me confirm there's no alternate momentum artifact supporting 1.05/13.5%, and inspect the Route B 30d audit + the table-generating script.

The Route B 30d economic numbers (Sharpe 0.740 momentum / 0.987 overlay, turnover, DD) trace cleanly to artifacts. But I notice the pipeline's own `selected_signal_metrics.csv` reports momentum test rank-IC as **negative (−0.0105, ICIR −0.588)** while the report shows **+0.0282 / +0.698** — a sign mismatch worth understanding. Let me verify the PDF page count, the overlay Sharpe (0.970 vs 0.987), and the ensemble table source.

Route B DSR/PBO (full-grid 0.003, same-target 0.814, PBO 0.50, bootstrap CI [0.019,1.796]) all trace cleanly. The overlay Sharpe is 0.987 in the audit but the report's Table `tab:route_b_30d` shows 0.970 — minor. Let me get a reliable page count and find the source of the main results table (Table `tab:results`).

Found it: the **model rows** in Table `tab:results` trace exactly to `horizon_comparison.md` (walk-forward pipeline: MLP 5d Sharpe 0.166, LightGBM 5d 0.236, Ridge 20d 0.755, etc.). But that table has **no momentum row**, and the IC/ICIR of the momentum row match the canonical 0.627 artifact while its Sharpe/return/turnover (1.05/13.5%/0.16) do not. Let me hunt for the provenance of the 1.05/13.5% momentum economics.

The momentum Sharpe "1.05/13.5%/0.16" appears **only** in the report and the improvement plan (路线A "净 Sharpe ~1.05") — no output artifact produces it. It's a legacy number never reconciled to the canonical 0.627 baseline. Let me get a reliable page count and skim the leakage/survivorship docs to finish the data-risk assessment.

Page count confirmed: **12 pages** (the stated limit is ≤10). Leakage controls are genuinely solid. One crucial thing to pin down before I finalize severity: the model rows in Table `tab:results` come from the walk-forward pipeline, but the canonical momentum (0.627) comes from a different evaluator. Let me check whether the walk-forward pipeline computes its *own* momentum baseline (there's a `baseline_score_test_backtest.csv`), which would tell me if the 1.05 is an internal-convention number or genuinely unsourced.

Key clarification: the pipeline's `baseline_score` is **not** the 12-1 momentum factor (turnover 0.086, negative Sharpe) — so the momentum row in Table `tab:results` is sourced from neither the model pipeline nor the canonical baseline. Let me pin down the sector 5d model rows and check whether correcting momentum could flip the "momentum beats every model" claim at the horizons shown.

The model rows are honest and traceable. The momentum row is the problem — and at **20d** the corrected momentum (~0.75, vs the table's inflated 1.12) would essentially tie Ridge-market (0.755), which could weaken the "momentum beats every model on Sharpe" sub-claim. Note also the table mixes families (5d=sector, 20d=market). Let me do two final checks: the ensemble table source and the survivorship doc.

I have enough verified evidence to deliver the review. I did read-only inspection and reconciled the report's headline numbers against the stored artifacts. Here are my findings as the Opus paper-level reviewer.

---

# Copilot Opus Review — `report/sp500_case_study.tex` (read-only, paper-first)

**Verdict:** The paper's *structure, honesty, and methodology hygiene are genuinely above-bar* (leakage controls, overlap correction, DSR/PBO, negative controls, honest demotion of graph/GAT/MLP/Kronos). The Route B overlay headline is well-sourced and correctly hedged. **But there is one P0 integrity break in the single most important table, plus a page-limit violation, that must be fixed before submission.**

---

## BLOCKER FINDINGS

### 🔴 P0-1 — The main hold-out table overstates the momentum baseline and is not reproducible from your own artifacts
**Where:** Table `tab:results` (lines 909, 914) and the "decisive test" sentence (§Results, line 553), echoed in §1 and `report_improvement_plan.md` Route A ("净 Sharpe ~1.05").

**Evidence:**
| Source | 5d sector momentum: Sharpe / Ann / Turn |
|---|---|
| Report `tab:results` | **1.05 / 13.5% / 0.16** |
| `output/momentum_baseline_priority/momentum_excess_sector_5d_sector_neutral.json` | **0.627 / 5.92% / 0.221** |

The row's Rank IC (0.024) and ICIR (1.06/2.10) **do** match the artifact, but Sharpe/return/turnover do **not** — the row is stitched from two sources. The 20d-market momentum (1.12 / 13.1%) matches **no** artifact (none exists beyond 10d; the 10d is 0.746). The "1.05/13.5/0.16" triple appears nowhere in `output/`.

**Why it's a blocker (paper claim):** "A simple momentum factor beats every trained model" is the paper's central humbling thesis and its conviction anchor. It survives on **IC/ICIR** (momentum 0.024 vs ≤0.013; 0.043 vs ≤0.029). But the **Sharpe** sub-claim is inflated ~67%, and it contradicts the *same report*: momentum Sharpe is 0.740 (Table `tab:route_b_30d`), 0.746 (`tab:residual_overlay`), 0.675 (`tab:sleeve_book`). Any reviewer who opens the JSON catches this instantly — fatal for a rigor-graded take-home. Worse, at **20d** the correct momentum (~0.75) essentially **ties Ridge-market (0.755** in `horizon_comparison.md`), so "beats *every* model on Sharpe" likely **fails at 20d** once corrected.

**Fix:** Regenerate the momentum rows from the canonical baseline under the *same evaluator as the models*; restate 5d≈0.63, 10d≈0.75; compute or drop the 20d row. Update line 553 / §1 to the real range and soften "wins on Sharpe" to "wins on IC/ICIR; competitive on Sharpe."

### 🔴 P1-2 — Headline table mixes evaluators and target families
Model rows come from the walk-forward pipeline (`horizon_comparison.md`); the momentum row from `eval_momentum_baseline.py`. You already document these two disagree on momentum Sharpe (0.802 vs 0.740, Table `tab:route_b_repro`) — so the headline comparison is **cross-convention**. The table also mixes families (**5d = sector, 20d = market**), which reads as cherry-picking. **Fix:** one evaluator, one family per horizon block, disclose convention.

### 🔴 P1-3 — Exceeds the stated ≤10-page limit
Compiled PDF is **12 pages** (verified); the take-home cap is 10 (improvement plan already flagged 11). **Fix:** graph/GAT + Kronos → one paragraph + appendix; merge the four overlapping momentum/overlay tables (`tab:route_b_30d`, `tab:route_b_repro`, `tab:residual_overlay`, `tab:p0audit`) into two.

---

## P2 (fix, non-blocking)
- **P2-4 — Overlay Sharpe drift:** `tab:route_b_30d` says overlay λ=0.2 Sharpe **0.970**; `tab:p0audit`/artifact say **0.987**. Reconcile and footnote which run.
- **P2-5 — Sign bug smell:** `alpha_robustness_audit_route_b_30d/selected_signal_metrics.csv` reports test momentum rank-IC = **−0.0105 (ICIR −0.588)** with *positive* Sharpe 0.740, while the report uses **+0.0282/+0.698** from the standard script. The Route B table's IC and economics come from different evaluators, and the pipeline's own IC sign looks wrong — verify before trusting the overlay's IC column.
- **P2-6 — Ensemble table not traceable:** `tab:ensemble` numbers (e.g., 0.852) aren't backed by a stored summary in `output/`. Emit an ensemble metrics CSV like Route B.

---

## Highest-ROI experiments (hours, current data only)
1. **Re-emit `tab:results`** (baseline + models) under one evaluator + one family — pure post-processing on existing predictions. Closes P0-1/P1-2.
2. **Add error bars:** Newey–West t-stat / bootstrap CI on momentum Sharpe *and* on each model−momentum Sharpe gap at 5d/20d. The report has almost no CIs outside Route B; this directly answers "is the gap real?"
3. **Compute 20d/30d momentum baselines** to source the 20d row and confirm whether Ridge-market ties momentum.
4. **PIT survivorship bound:** rerun momentum + Route B on the `date_added`-included subuniverse for a *data-driven* (not just parametric short-side) survivorship sensitivity.

---

## Wording / table / figure changes
- Replace every "net Sharpe 1.05" with the corrected same-convention number; stop implying momentum Sharpe >1.0.
- Lead the abstract with the overlay's **deflated** status (full-grid DSR 0.003, PBO 50%) in the same sentence as the raw 0.97 Sharpe — currently the deflation lands a beat later.
- Disclose evaluator/convention wherever baseline and models appear together (today only disclosed for Route B).
- Standardize figures (mix of `.pdf` and `.png`); confirm all 6 `\includegraphics` resolve in the 10-page rebuild.

## Residual risks (acceptable, disclosed)
Single 2022–2026 momentum-friendly hold-out (CPCV distribution still TODO); factor neutralization limited to price/volume+sector (correctly scoped); survivorship is a bound, not a correction.

---

**Gate status:** I ran as the read-only Copilot Opus reviewer. The `manual_review` MCP browser handoff is not exposed in this runtime, so this is the direct Opus review; I performed only read-only artifact verification (no files edited, nothing committed). **One P0 (momentum-table integrity) and two P1 blockers (cross-evaluator table, 12-page overrun) must be resolved and re-reviewed before submission.** The underlying research story — momentum is the robust core, Route B is an honest, deflation-aware residual sleeve — is credible and survives the fixes; it's the headline *numbers and packaging*, not the thesis, that block.
