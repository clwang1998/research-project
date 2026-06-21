I'll start by exploring the repository structure and reading the key files for this paper-level review.

Let me read the main report in sections and explore the directory structure.

Let me continue reading the report and key docs in parallel.

This is a sophisticated, deflation-first report. Let me continue reading the report body and the key audit docs.

Let me read the rest of the report and the triage/improvement-plan docs.

Let me read the final report sections and the remaining key docs.

I have a thorough understanding of the report now. Let me verify the artifacts referenced actually exist and check key numbers against outputs.

Let me verify the key numbers against the actual artifacts and check the PDF page count.

Numbers match. Let me verify the IC robustness, momentum baseline bootstrap, the robustness audit, and the PDF page count.

Let me get the page count properly and verify the DSR/PBO audit numbers.

Page count is 10 (within limit). Let me check the DSR/PBO CSVs for the Route B audit.

All headline numbers reconcile with artifacts exactly. Let me verify the canonical IC artifact, traded-horizon t-stats, and that figures exist.

All artifacts reconcile precisely. Let me verify the PIT survivorship sensitivity numbers and check whether a sector-relative 20d momentum row exists (the results table mixes market/sector-relative).

Let me read the PIT sensitivity summary numbers from the saved output.

I've read the report end-to-end and reconciled every headline number against the underlying artifacts. All figures exist, the PDF is 10 pages (within limit), and the metrics in the LaTeX tables match the CSV/JSON sources exactly. Here is my read-only review.

---

## Reviewer verdict

**No P0 paper-level blockers.** The headline is deliberately negative ("no statistically deflated alpha beyond 12–1 momentum"), and that claim is *fully supported* by the reconciled evidence (DSR full-grid 0.003, PBO 0.50, paired increment t=0.25, FM t=0.05). This is the rare submission where the risk is **under-claiming and weak conviction**, not overclaiming. Everything I could check reproduces. Below are the issues that would most affect whether a PM finds the paper *credible and hireable*.

---

## Blocker / priority findings

### P1-1 — Benchmark significance is at 1-day, but the headline book is 30-day (horizon mismatch)
- **Where:** §1 abstract (lines 79–86), Table `tab:route_b_30d`, Table `tab:results` 30d block.
- **Issue:** Momentum's status as "the core benchmark every model must beat" is anchored on the **1-day** cross-sectional IC (plain t=3.54, NW-21 t=4.39). But the entire Route B comparison and the tradable book are at **30 days**, where the portfolio mean-return t=1.51 with bootstrap Sharpe CI **[-0.22, 1.85] (crosses zero)**, and the traded-horizon IC block-bootstrap CI also crosses zero (low = -0.0022, verified in `momentum_ic_traded_horizons`). So the benchmark is *not* significant at the horizon you actually tabulate and trade.
- **Impact on claim:** A PM will say "you're defending the whole conclusion with a 1-day IC you don't trade, while the 30-day book you headline isn't significant."
- **Fix:** Lead the *tradable* claim at 5d (block-boot t=2.41, Sharpe 0.63, turnover 0.22) where momentum is genuinely significant; demote 30d to a horizon-robustness row. State explicitly: 1-day IC = signal-existence evidence; net-of-cost tradability is horizon/cost-limited.

### P1-2 — Survivorship contaminates the one endorsed signal, and the partial PIT check nearly halves it
- **Where:** §Data (119–128), §Discussion survivorship (894–913), buried in one row of Table `tab:p0audit`.
- **Issue:** The paper recommends 12–1 momentum — precisely the signal most exposed to survivorship. The disclosed inclusion-only PIT filter cuts momentum **Sharpe 0.741 → 0.446** (ann. return 7.79%→3.91%, DD -13.8%→-17.5%). That ~40% haircut is the single most important robustness number in the paper and is currently a footnote-level table row.
- **Impact on claim:** The core recommendation is conditional on a survivorship fix; even a *partial, inclusion-side* check materially weakens it. Not foregrounding this looks like minimizing the paper's own biggest caveat.
- **Fix:** Promote to the abstract and Limitations. State the endorsed signal's survivorship-aware net Sharpe is ≈0.45, not 0.74, and that the short side (missing delisters) is unquantified.

### P1-3 — Self-refuting deflation kills conviction (the "would-we-hire" risk)
- **Where:** Abstract and throughout Results/Discussion.
- **Issue:** Every positive result is negated in the same sentence; the paper reads as "I proved I'm honest but produced no alpha." This is your own improvement plan's B-/C+ diagnosis (`report_improvement_plan.md` §0, §2.2.8).
- **Fix:** Open with a crisp PM decision — *trade low-turnover 12–1 momentum at 5–20d; here is the survivorship-aware net Sharpe + capacity; ML/graph/residual add no deflated alpha; next research dollar → point-in-time universe + delisting returns* — then let the deflation evidence **support** that decision instead of drowning it. Keep the rigor; reorder so the decision leads.

### P2-1 — Table `tab:results` mixes target families (mild disclosed cherry-pick)
The 20d row is **market-relative** (IC 0.042) while 5d/30d are sector-relative. A sector-relative 20d momentum exists with **identical Sharpe 0.822** but lower IC (0.030). Showing the market-relative IC makes 20d momentum look stronger. Fix: use sector-relative throughout the momentum rows, or split market-relative model rows into a separate panel.

### P2-2 — Dual IC convention invites alarm
The audit's primary file `selected_signal_metrics.csv` reports momentum test rank IC = **-0.0105** (residualized-label convention); the headline table uses **+0.0282** (canonical raw-label). Both are disclosed, but a reviewer hitting the audit CSV first sees momentum with negative IC. Fix: make canonical raw-label the single table convention; relegate the residualized-label IC to a clearly-labeled diagnostic footnote (the negative sign is mechanical — the label has momentum partly removed).

### P2-3 — PBO = exactly 0.50 / traded-horizon CIs cross zero
PBO=0.50 (28 strategies, 20 splits) literally means the selected config is *median* OOS — consistent with "no alpha"; keep but don't let it read as a near-miss. Also quote the traded-horizon block-boot CIs (20d/30d cross zero) where you currently only give t≈1.89/1.85 — consistent with the paper's own rigor elsewhere.

---

## Focused experiments (current data only, a few hours each)

1. **Lead-horizon swap (re-tabulation only):** Promote 5d/10d sector-relative momentum as the headline tradable signal with block-boot t, net Sharpe, turnover, and the existing capacity curve. Highest ROI; no new compute.
2. **Survivorship-aware headline number:** Report PIT-inclusion momentum Sharpe (0.45) + parametric delisting band as *the* endorsed figure, and add a directional long-vs-short decomposition of which book side the missing names hit (uses `date_added` + existing returns).
3. **Momentum IC decay/half-life (1→30d)** from the existing daily rank-IC series, to justify the traded horizon economically rather than by selection.
4. **Fama–MacBeth of momentum itself** (NW SE) at the traded horizon — you give the *overlay* an FM t but never the benchmark; this would let momentum's marginal t stand on its own.

---

## Wording / table / figure changes for the final report

- Rewrite the abstract to **lead with the decision + survivorship-aware momentum number**, then the caveats.
- Foreground the **0.741→0.446 PIT haircut** in abstract and Limitations.
- Make Table `tab:results` target-family-consistent; add CI columns wherever a t-stat is quoted.
- State the **1-day-IC vs 30-day-book** distinction explicitly in §1 and in the `tab:route_b_30d` caption.
- Standardize all tables on canonical raw-label IC; footnote the residual convention as a diagnostic.
- One line demoting graph/GAT/Kronos/MLP is already honest — keep it; ensure Kronos stays labeled "future data-universe route, not evidence" (currently correct).

---

## Residual risks (no blocker, but flag in the paper)
- **Reproducibility caveat I could not clear:** I verified outputs reconcile with the LaTeX, but did not re-execute the pipeline; the leakage controls (execution lag, two-sided purge, embargo, train-only fit) are described and the report states a no-embargo diagnostic inflates metrics — take that as asserted, not independently re-run here.
- **Dividend adjustment** uncertainty remains a (minor, disclosed) data-quality risk on all return targets.
- **Single OOS regime (2022–2026, momentum-friendly):** hold-out conclusions are regime-conditional; the walk-forward stability figure mitigates but does not eliminate this.

**Copilot Opus reviewer gate:** ran here directly as the read-only paper reviewer; the `mcp__manual_review__review` tool is not exposed in this runtime, so this constitutes the manual Opus review pass. No files were edited. Recommend saving this under `review-stage/`.

