I'll start by inspecting the repository structure and the key files for this paper review.

Let me read the main report and key supporting docs in parallel.

Good context. Let me continue reading the report and the triage/improvement docs.

Let me read the rest of the report (results, discussion sections) and the improvement plan.

Now let me read the discussion/limitations/conclusion and check the reviewer MCP doc and output summaries.

Let me read the final section, the reviewer MCP doc, and verify key output artifacts.

I've read the full report. Now let me verify key numerical claims against the underlying artifacts.

Let me check the momentum baseline JSON files directly and the paired increment / PIT artifacts.

Let me verify the load-bearing positive claim — the 5d traded-horizon IC t=2.41 — and the daily IC robustness and PIT sensitivity.

Strong verification so far — the DSR/PBO/FM/paired numbers all tie out to artifacts. I found the critical tension: the only significant traded-horizon result (5d t=2.41) sits entirely in the 2022–26 window the paper itself calls momentum-friendly. Let me check page count, figure existence, and the portfolio-uncertainty artifact.

All numbers tie out precisely. The regime artifact confirms 5d momentum was significantly *negative* in 2008–11 (t=−1.90). Let me confirm the PDF page count (a hard submission constraint) and check the route_b selected-signal metrics.

Verification complete. Every load-bearing number ties out to the artifacts, the PDF is exactly **10 pages** (constraint met), and all six figures exist. I have what I need to deliver the review.

---

# Copilot Opus — Read-Only Quant PM / Senior Researcher Review

**Gate status:** This *is* the read-only Opus review. I inspected files directly (MCP `manual_review` not invoked); no files edited, no commits. Numerical claims were cross-checked against `output/` and `report/artifacts/` CSV/JSON.

**Bottom line:** This is an unusually honest, internally consistent triage paper. **I found no P0 blocker where a headline claim contradicts its evidence** — the authors have pre-empted most overclaiming by hedging heavily. The real problems are P1/P2: the headline leads with the *most regime-fragile* significant number, the conviction chain has two stacked weak links the prose under-foregrounds, and the narrative signal-to-noise is inverted. Details below.

---

## Blocker findings

### P1-1 — The endorsed benchmark's only significant *tradable-horizon* evidence is confined to the regime the paper itself calls momentum-friendly
**Where:** §1 (lines 70–73, 94–101), `tab:momentum_ladder`, `momentum_regime_diagnostics.csv`, `momentum_ic_traded_horizons_5d_split/`.
**Evidence:** 5d traded IC is significant **only** in 2022–26 (block-boot t=2.41, CI [0.004,0.042]). In discovery 2008–21 it is insignificant (t=1.12, CI [−0.0045,0.0169]). The regime artifact shows 5d momentum Sharpe = **−0.95 (mean-return t=−1.90, significantly negative)** in 2008–11, +0.33 (2012–16), −0.14 (2017–21), +0.62 (2022–26).
**Impact on claim:** The abstract leads with t=2.41 — the significant number with the *weakest provenance*, since it lives in the favorable test window. "Signal exists" is genuinely supported (1d discovery block-boot t=2.42, CI [0.0013,0.0119]), but "**tradable** at 5d" is demonstrated only in-regime. The paper separates these pieces but never states the uncomfortable synthesis plainly.
**Fix:** Lead the headline with the 1d *discovery* IC (the real out-of-regime evidence), explicitly demote t=2.41 to "regime-contingent," and add one sentence: *the tradable-horizon edge is not established outside 2022–26 and was significantly negative in 2008–11.*

### P1-2 — After the only feasible survivorship correction, the endorsed book's Sharpe CI crosses zero — this should be the binding headline constraint, not a §-Discussion footnote
**Where:** §Data (144–154), §Discussion (955–983), `tab:results` caption, `pit_inclusion_sensitivity_5d/`.
**Evidence:** PIT inclusion filter cuts 5d Sharpe 0.620→0.461 with CI **[−0.49,1.43]** (crosses zero). The deleted-loser short-leg effect is unquantified. So *both* identified survivorship effects are adverse, and after the single correction the authors can actually compute, the portfolio Sharpe is statistically indistinguishable from zero.
**Impact:** The fundability conclusion ("size off IC stability, not Sharpe") leans on IC stability — but per P1-1 that stability is itself regime-confined. Two weak links are stacked; the paper presents them ~600 lines apart, softening the combined force.
**Fix:** Surface in §1 that the recent-regime Sharpe edge does not survive the inclusion-side PIT filter, and that this — not cost/borrow — is the primary reason the signal is "not fundable as-is."

### P2-1 — Momentum traded-IC t=2.41 is a max over horizon × target and is not deflated, while the ML grid is charged 884 trials
**Where:** §Results (542–547), `momentum_traded_horizon_ic_robustness.csv` (block-boot t = 2.41/2.13/1.89/1.85 across 5/10/20/30d).
**Impact:** Asymmetric rigor: rigorous DSR on ML, raw t on the chosen-because-best-horizon momentum number whose CI lower bound (0.004) is already fragile. Defensible (momentum is pre-registered) but a skeptical PM will dock it.
**Fix:** One sentence acknowledging 5d was the max-t horizon pick; optionally a light horizon×target selection haircut.

### P2-2 — Two IC conventions coexist and create a cross-reference trap
**Where:** `route_b_canonical_ic` (momentum RankIC **+0.0282**) vs `alpha_robustness_audit_route_b_30d/selected_signal_metrics.csv` (momentum RankIC **−0.0105**, residualized-label convention).
**Impact:** A reviewer cross-referencing the audit CSV sees momentum IC flip sign. The report flags it (route_b doc lines 38–40) but the raw artifact is a trap.
**Fix:** One prominent signpost in §Results that the audit CSV uses residualized labels; cite the canonical number as authoritative.

---

## Focused experiments that would most improve the report (each a few hours, current data only)

1. **CPCV / multi-regime Sharpe distribution for the 5d momentum book.** Momentum is no-fit, so it can be combinatorially resampled cheaply — directly answers P1-1. The paper admits saved *overlay* predictions can't support a pre-2022 distribution, but the *benchmark* can. Highest ROI: converts "regime-confined point estimate" into an honest distribution.
2. **Bound the short-leg survivorship effect.** You did inclusion-side PIT + a whole-book delisting haircut, but never the specific prior-loser short-leg channel. A crude bound (assume *k* deleted names/yr enter the short decile at −X%) puts the *other* sign on the table and lets you state a true interval rather than "net sign unidentified."
3. **Horizon×target deflation of the momentum traded-IC** (you already have all 8 cells) — closes P2-1 in minutes.
4. **One external reference Sharpe** for net cross-sectional 12–1 momentum (~0.5–1.0 in literature) so the PM has a yardstick for 0.62. Addresses the report's own missing-benchmark P2.

---

## Wording / table / figure changes for the final report

1. **Invert §1's caveat density.** Open with one clean sentence (signal + the single most defensible number = 1d discovery IC), *then* caveats. Currently every positive statement is self-negated in the same clause — the improvement plan flagged this ("叙事自我证伪"); it still reads as arguing you found nothing. Honesty ≠ inverted signal-to-noise.
2. **Promote the PIT-inclusion "CI crosses zero" result into §1** as the funding blocker (P1-2).
3. **Reconsider the greyed LightGBM 30d Sharpe=1.23 row in `tab:results`.** It is the largest Sharpe in the headline table and labeled "not a result." Either drop it or compress the caveat — as printed it invites the exact misread the paper spends a page preventing.
4. **State the regime-confinement explicitly** in `tab:momentum_ladder` (the "Regimes" row lists the slices but doesn't draw the conclusion that significance is regime-contingent).
5. **Add the IC-convention signpost** (P2-2).

---

## Residual risks (no P0, stated explicitly)

- **No P0 paper-level blocker:** claims match artifacts; leakage controls (T+1 lag, two-sided purge, embargo, train-only fit), overlap correction, and the DSR/PBO/FM/paired-increment numbers all reproduce. Failed methods (GAT placebo-beats-real, MLP, Kronos, seed-bag, Kaggle agg) are framed honestly and not overpackaged — exemplary.
- **Structural risk the paper correctly cannot close:** no PIT universe + delisting returns ⇒ the headline is a research benchmark, not deployable alpha. This is acknowledged; just keep it foregrounded.
- **Conviction risk:** as a *PM pitch*, the deliverable conclusion is "nothing here is fundable without better data." Defensible and honest for a take-home, but the report should own that framing confidently rather than burying conviction under stacked hedges.

