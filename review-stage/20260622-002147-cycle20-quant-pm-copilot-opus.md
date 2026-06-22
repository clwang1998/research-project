I'll review this as a quant PM reviewer. Let me start by inspecting the repository structure and the key files.

Let me read the main report and the key review docs.

I've read the full report. Now let me cross-check the supporting docs and output artifacts.

Now the triage and improvement plan docs, plus key output artifacts to verify cited numbers.

Let me verify the key numbers against the output artifacts. Let me explore the artifacts referenced in the report.

Numbers tie out so far. Let me verify the DSR/PBO audit numbers, the 884-trial count, and capacity figures.

Strong reproducibility so far. Let me verify daily IC robustness, PIT sensitivity, cost breakeven, the 884-trial provenance, and check the PDF page count (the plan flagged a 10-page limit).

Excellent reproducibility — every cited number ties to artifacts. Let me check the PDF page count (plan flagged a 10-page limit), confirm figures exist, and look at the vol-timing negative control.

Let me verify a key concern: whether the headline traded-horizon IC (t=2.41) is computed only on the favorable 2022–2026 hold-out, and check the turnover annualization framing.

Let me confirm the annualized turnover calculation and check whether the report ever discloses the rebalance-frequency caveat for its "lowest turnover" claim.

Confirmed an important framing issue. Let me check prior review rounds and the reviewer doc for context before finalizing.

There's extensive prior review history. Let me read the two most recent cycle reviews to avoid repeating resolved items and confirm my findings are current.

I've completed an independent review—reading the full report and recomputing every headline number against the source artifacts. All numbers reconcile, prior-cycle fixes landed, and I found two new framing issues. Here is my review.

---

# Copilot Opus — Read-Only Quant PM / Senior Researcher Review
**Deliverable:** `report/sp500_case_study.tex` → `.pdf` (**10 pages**, meets ≤10 limit).
**Gate note:** Ran as the Copilot Opus read-only reviewer **directly** (MCP browser handoff not invoked). **No files edited; no commands beyond inspection.**

## Reproducibility check — PASSED (recomputed from artifacts, not prose)
Every load-bearing number traces to a source file: momentum 5d/20d/30d Sharpe **0.627/0.822/0.740**, RankIC **0.0234/0.0300/0.0282**; traded-horizon block-boot t **2.41/2.13/1.89/1.85** (20d/30d IC CIs cross zero); 1d IC t **3.54**, NW-21 **4.39**, CI **[0.0115,0.0297]**; paired increment gap **0.246**, t **0.248**, corr **0.932**; DSR **0.003**(N=884)/**0.814**(N=14); PBO **0.50**; FM t **0.048**; capacity $1B Sharpe **0.864** / p95 **25.3%**; PIT 5d **0.620→0.461**, 30d overlay **0.987→0.725**. No fabricated number, no leakage/horizon-misalignment defect. Cycle-18/19 fixes confirmed landed (vol-timing control added, 30d-specificity language added, $395M 10%-ADV ceiling added, DSR-fails-all-framings stated).

---

## Blocker findings

### P0 — none
No blocking paper-level integrity defect. The paper does not claim ML beats momentum, frames Route B as drawdown-dampening not alpha, and honestly demotes graph/GAT/MLP/Kronos/seed-bag. It under-claims if anything.

### P1-A — The "lowest turnover" pillar for 5d is **inverted on annualization** *(NEW — not in any prior round)*
- **Where:** §1 l.67–69, l.92–98; `tab:momentum_ladder` l.861; Conclusion l.1056 — all endorse 5d partly because "turnover is lowest (0.22)."
- **The defect:** 0.22 is **per-rebalance** turnover. The 5d book rebalances **50.4×/yr**, the 30d book **8.4×/yr**. Annualized one-way turnover is **5d ≈ 1115%, 20d ≈ 449%, 30d ≈ 337%** (`momentum_portfolio_uncertainty.csv`: 0.221×50.4, 0.356×12.6, 0.401×8.4). **5d is the highest annual-turnover book by ~3.3×, not the lowest.** The cross-horizon turnover comparison is apples-to-oranges and points the opposite way from how it's used.
- **Impact on claim:** Turnover is one of only **two** endorsement pillars (IC + turnover), and the PM decision (l.1063–1065) explicitly says "size off IC stability and turnover." A PM reading "5d, turnover 0.22, lowest among tested books, most fundable" gets the capacity/cost intuition backwards — 5d is the *most* trading-intensive and *least* capacity-friendly of the three. Net Sharpe already pays this cost (which is *why* 5d's 0.627 is the **lowest** of the three horizons), so the economic conclusion isn't broken, but the stated justification is.
- **Fix:** Report **annualized** turnover alongside per-rebalance, or explicitly label 0.22 as per-rebalance and note 5d rebalances 6× more often. Drop turnover as a *reason to prefer* 5d; the honest 5d case is the IC argument (P1-B), not turnover.

### P1-B — 5d endorsement rests on a thin reed; 20d dominates on the metrics the paper says it values *(NEW, related)*
- **Where:** §1 l.92–110 selects 5d over 20d/30d.
- **The tension:** **20d beats 5d on net Sharpe (0.822 vs 0.627), on RankIC (0.0300 vs 0.0234), and on annualized turnover (449% vs 1115%).** The sole legitimate argument for 5d is that its block-boot IC CI **excludes zero [0.004,0.042]** while 20d's **barely crosses** ([−0.0013,0.063]) — but 20d's CI-low is essentially touching zero, and 20d retains higher absolute Sharpe even post-PIT (0.513 vs 0.461). The endorsement of 5d over 20d therefore hangs almost entirely on a CI that brushes zero by 0.0013.
- **Impact:** The headline horizon choice is more fragile than presented. A reviewer/PM could reasonably prefer 20d.
- **Fix:** State plainly that 5d is chosen for **signal-existence reliability** (IC CI cleanly excludes zero + strongest 1d confirmation + best *relative* PIT retention), explicitly acknowledge 20d's higher Sharpe/IC, and frame it as "I size off the horizon where the signal is most reliably non-zero, accepting lower point-Sharpe." That is defensible; the current turnover-based framing is not.

### P1-C — The headline **traded-horizon IC is computed only on the favorable 2022–2026 hold-out** *(NEW/sharpened)*
- **Where:** Abstract l.70–71 and `tab:momentum_ladder` lead with "traded 5d block-bootstrap IC t=2.41, CI [0.004,0.042]." `momentum_ic_traded_horizons/README.md` confirms the file "keeps the 2022+ hold-out rows" only — n_dates **1111** = identical to the `post2022_holdout` regime slice.
- **The defect:** The report's own calendar-slice table shows 5d momentum Sharpe is **−0.95 (2008–11), 0.33 (2012–16), −0.14 (2017–21), 0.62 (2022–26)** — negative in two of four regimes — and it calls 2022–26 "momentum-friendly rather than representative." Yet the load-bearing *traded* IC statistic is measured **only in that friendly window**, with **no discovery-period (2008–2021) traded-horizon IC** shown as a counterweight. The 1d IC has a discovery row (t=2.23) for balance; the traded 5d/10d/20d/30d IC does not.
- **Impact:** The strongest "signal exists *and is tradable*" evidence is concentrated in the regime the paper concedes is favorable. This is disclosed in general terms but not at the point of the claim, which slightly overstates the headline.
- **Fix:** Compute the 5d traded block-boot IC t on 2008–2021 (one run over existing parquet) and report it next to 2.41, **or** explicitly label "t=2.41 is hold-out-only; the favorable-regime caveat applies to this statistic specifically."

### P2-A — Self-defeating narrative persists *(carried; still live)*
Structure improved (headline-first §1, evidence ladder), but most positive results are still killed in the same sentence. For a take-home this risks reading "found nothing" rather than "has the judgment to know what's real." **Fix:** one consolidated "Robustness verdict" box; lead each result with the decision it drives; one unhedged conviction sentence in §1.

### P2-B — Route B occupies a large page budget for a confirmed null *(carried)*
The 30d overlay gets a full results table, the P0 audit table, paired-increment, cost-breakeven, capacity, and survivorship rows — for a result the paper itself concludes is statistically indistinguishable from momentum (t=0.25, corr 0.93, fails DSR under all framings). Demotion is correct in *words* but not in *space*. **Fix:** compress Route B to one table + one verdict paragraph; reclaim space for the 5d momentum CPCV (experiment #1).

---

## Focused experiments that would most improve the report (each ≲ a few hours, current data only)

1. **Discovery-period traded-horizon IC for 5d momentum (resolves P1-C, highest ROI).** Re-run `build_momentum_ic_robustness.py` on 2008–2021 for `target_excess_sector_fwd_5d`. Reports whether the t=2.41 tradable-signal claim holds outside the favorable regime. One command; directly de-risks the headline.
2. **Annualized-turnover row in `tab:results` (resolves P1-A).** Add `turnover × 252/h` (1115%/449%/337%). Pure post-processing; flips the turnover narrative to honest and strengthens credibility.
3. **CPCV / combinatorial-purged Sharpe distribution for the no-fit 5d momentum book.** Momentum needs no fitting → recompute on every purged path → converts the four regime point estimates into a distribution and directly answers "single lucky regime" (paper concedes "calendar slices, not CPCV proof," l.1013–1020).
4. **5d Route B overlay** (closes the horizon-incoherence gap definitively rather than only in prose). If it doesn't help the endorsed book, that's a clean honest result.

*(Already done — do not re-request: vol-timing control, cost break-even ≈147 bps, borrow sensitivity, PIT inclusion, paired increment.)*

---

## Wording / table / figure changes for the final report
- **§1, `tab:momentum_ladder`, Conclusion:** stop citing "lowest turnover" as a reason to prefer 5d; report annualized turnover and re-base the 5d case on IC reliability (P1-A/B).
- **Abstract + ladder:** label the traded **t=2.41 as hold-out-only** (P1-C).
- **§1 select-5d logic:** add one sentence acknowledging 20d's higher Sharpe/RankIC and why you still pick 5d (P1-B).
- **Narrative:** consolidate per-paragraph kill-shots into one "Robustness verdict" box; add one unhedged conviction sentence (P2-A).
- **Route B:** compress to one table + verdict (P2-B).

---

## Residual risks (acknowledged, not blocking)
- **Survivorship** is inclusion-side only; deletion side is parametric. Net-sign-indeterminate framing (l.969–980) is correct — keep it.
- **N=35** non-overlapping periods underlies every Route B economic claim — irreducibly thin, honestly disclosed.
- **DSR family size (884)** is a judgment call, not a theorem — the paper says so.
- **Single-evaluation hold-out** is one momentum-friendly regime; experiment #3 (CPCV) is the cleanest remaining mitigation.

**Bottom line: Submit-ready on integrity and reproducibility — no P0.** The new, material gap is that the **turnover justification for the endorsed 5d benchmark is inverted on annualization (P1-A)** and the **headline traded IC is favorable-regime-only (P1-C)**; both are wording/one-run fixes, not data defects. Fixing P1-A/B/C + running experiments #1–#3 moves this from "rigorous triage" to "credible, coherent PM-facing research." **Outcome: PASS with P1 framing fixes recommended.**

