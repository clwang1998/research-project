I'll review this as a quant PM evaluating whether the paper is credible enough to submit. Let me start by exploring the repository structure and reading the key files.

Let me read the main paper and key documents in parallel.

Let me read the full paper in sections.

I've read the full paper. Now let me cross-check the supporting docs and output artifacts to verify the claims. Let me read the key documents in parallel.

The docs are consistent with the paper. Let me read the triage/improvement plan docs and verify key numbers against the actual output artifacts.

Now let me verify the key numbers against the actual output artifacts and check the report's artifacts directory.

PDF is exactly 10 pages (within limit). Let me verify the key statistical artifacts that underpin the headline claims.

Excellent — the headline numbers (t=0.25, corr=0.93, momentum t=1.51, NW lag-21 t=4.39, traded-horizon block-bootstrap t's) all tie out to the artifacts. Now let me verify the DSR/PBO audit numbers and check for any cross-table inconsistencies.

All audit numbers (DSR 0.003/0.814, PBO 50%, FM t=0.05, capacity, survivorship) verify exactly against artifacts. The paper is exceptionally well-documented. Let me check two things that affect paper-level claims: whether a `date_added` point-in-time inclusion backtest exists (survivorship), and scan for any cross-table numeric inconsistencies.

Key finding: `date_added` is populated for all 503 names, and `make_features.py` computes a `sp500_member_asof` flag. 72 names were added in 2022+. Let me check whether the actual backtests apply this point-in-time inclusion filter, or only use the parametric delisting haircut.

Confirmed important gap: `sp500_member_asof` is computed as a feature but **never used as a universe filter** anywhere. Let me confirm this isn't applied in the core pipeline and quantify the hold-out exposure.

72 names (14% of the universe) joined the index during the 2022–2026 hold-out, yet the backtest trades all 503 current members across it. Let me do a final confirmation on the pipeline universe construction and verify all referenced figures exist.

I've verified every headline statistic against archived artifacts and traced the survivorship handling through the code. Here is my review.

---

# Copilot Opus — Read-Only Quant PM / Senior Researcher Review
**Paper:** `report/sp500_case_study.tex` (10 pages, within limit). All six referenced figures exist.

**Verdict:** This is a credible, submittable deflation-first negative-result paper. Every headline statistic ties out exactly to archived artifacts (I re-checked the momentum baseline JSON, paired-increment, DSR/PBO, Fama–MacBeth, capacity, survivorship, and daily/traded-horizon IC CSVs). The paper *under-claims* rather than overclaims, and the conclusions follow from the evidence. **There are no P0 blockers that falsify a stated claim.** The issues below are about completeness of the robustness story and PM-level presentation, not correctness.

## Blocker findings

### P0 — None
No stated conclusion is contradicted by the data. Cross-checks that passed:
- Momentum daily IC OOS: plain `t=3.54`, NW lag-21 `t=4.39`, block-boot CI `[0.0115, 0.0297]` → matches `momentum_ic_robustness/`.
- Paired increment: `t=0.25`, corr `0.93`, Sharpe gap `+0.246`, overlay MaxDD `-7.32%` → matches `route_b_paired_increment/`.
- DSR full-grid `0.003` (884 trials, null max 1.512), same-target `0.814` (14 trials), PBO `50%`, FM `t=0.05` → matches `alpha_robustness_audit_route_b_30d/`.
- 30d momentum baseline (Sharpe 0.740, ret 7.78%, MaxDD −13.83%, turnover 0.401) reproduces exactly.

### P1 — Survivorship robustness is half-delivered; an *available* point-in-time check is left on the table
**File/section:** Data §"Survivorship bias"; Discussion §"Survivorship bias"; Table `tab:p0audit`; `scripts/run_alpha_robustness_audit.py` (lines ~550–626).
**Finding:** `date_added` is populated for **all 503** names and `make_features.py` already computes `sp500_member_asof` and `sp500_membership_age_years`. **But `sp500_member_asof` is never used as a universe filter** — not in `eval_momentum_baseline.py`, `run_model_pipeline.py` (only `apply_liquidity_universe`), or the robustness audit. **72 names (14% of the universe) joined the index on/after 2022-01-01**, so the 2022–2026 hold-out trades names *before they were index members* (forward-membership/inclusion bias). The paper's survivorship treatment is therefore only a *parametric* delisting haircut, while the inclusion-side PIT check the data fully supports was not run.
**Impact on the paper:** Does not overturn the negative thesis, but it (a) weakens the credibility of "we did the best survivorship treatment the data allows," (b) is the paper's own improvement-plan item P0-4, delivered only in its haircut half, and (c) could move the *relative* numbers the paper leans on — the Route B drawdown story (−13.8% → −7.3%) and momentum-vs-ML ranking — since recently-added names cluster in the hold-out.
**Fix (≈1–2h):** Re-run the 30d momentum baseline + Route B overlay with `universe = sp500_member_asof==1` and report the delta vs the current current-membership run. Reframe the section as "PIT-inclusion robustness (available) + delisting haircut (parametric, sign unidentified)."

### P1 — Abstract buries the decision under a wall of deflation
**Section:** §1 "Headline design" paragraph.
**Finding:** The first paragraph is rigorous but is a dense stack of t-stats/CIs (0.25, 3.54, 4.39, 2.41/2.13/1.89/1.85, [−0.22,1.85]) before the reader reaches a decision. The team's own `report_improvement_plan.md` (§2.2 item 8, §7–§8) explicitly warned against "narrative self-falsification." The conviction *is* present (trade low-turnover momentum; ML adds no deflated alpha; spend next research dollar on PIT universe) but is hard to extract in the first three sentences.
**Impact:** A PM skimming the abstract struggles to extract the call. Pure presentation; no number changes.
**Fix:** Lead with one conviction sentence — *"On price/volume + sector alone, the only robustly tradable signal is low-turnover 12-1 momentum (net Sharpe ≈0.6–0.8 by horizon); no ML/graph/MLP/residual construction adds statistically deflated alpha, so the recommendation is to trade momentum with strict cost/turnover control and spend the next research dollar on a point-in-time universe"* — then the deflation evidence.

### P2 — Minor polish
- **Annualization convention:** Paper Tables 3–4 use *arithmetic* annualization (mom 7.78%, overlay 8.27%, Δ0.50%) — internally consistent. The artifact `route_b_paired_increment/paired_increment_summary.csv` *also* stores *geometric* figures (7.48%/8.22%). Identical Sharpe (0.7403) confirms it's the same return stream. No paper error; add a one-line footnote noting the two conventions to pre-empt confusion.
- **DSR null pooling:** The 884-trial expected-max null (1.512, σ_SR=0.469) pools heterogeneous horizons/targets into one per-observation Sharpe σ. This is *conservative* (penalizes the overlay), so it supports the humble conclusion — but add one sentence acknowledging the pooled-trial approximation rather than implying clean comparability.
- **Table 4 mixes target families** (20d market-relative; 5d/30d sector-relative), each the "best archived validation family." It's disclosed and inflates the *benchmark* (conservative vs ML), but add a one-line justification for the per-horizon family choice to pre-empt the obvious question.
- **IC scan starts 2008, panel starts 2000** — state why (post-GFC/warmup) so it doesn't read as a silent sample trim.

## Focused experiments (highest ROI, current data only)
1. **PIT-inclusion re-run (P1-1).** Gate the universe on `sp500_member_asof==1`; report momentum + Route B deltas. Single biggest credibility lever; data already present.
2. **Hold-out Sharpe *distribution*, not a point.** Block-bootstrap / CPCV the 30d momentum book across 2022 selloff vs 2023–24 momentum-friendly sub-windows (improvement-plan P1-3). Directly answers "the hold-out is one momentum-friendly regime."
3. **Momentum IC decay / half-life** across h∈{1,5,10,20,30,…} on the hold-out. Cheap; substantiates "daily IC is the real anchor, 30d portfolio Sharpe is thin."
4. **A reference yardstick** for the momentum Sharpe (passive long-only top-decile, or the equal-weight mom+reversal sleeve already computed) surfaced as one line, so 0.74 has a comparative anchor.

## Wording / table / figure changes
- Rewrite the abstract conviction-first (P1-2).
- Survivorship §: add the PIT-inclusion re-run result; explicitly state the haircut addresses only the *delisting* side and its sign is unidentified for a long–short tilt.
- Table 4: footnote the per-horizon target-family selection.
- Add the two-convention annualization footnote (P2).
- Keep demoting the non-selected 30d LightGBM (Sharpe 1.23) — currently handled correctly; ensure it never reads as a headline.

## Residual risks (acknowledged, not blocking)
- 30d portfolio inference rests on **N=35** non-overlapping periods (momentum `t=1.51`); the paper correctly anchors momentum on daily IC instead — keep that framing.
- Delisting-side survivorship remains **uncorrectable** with this dataset (needs external PIT constituents + delisting returns); the paper is honest about this.
- The full 884-trial grid is **GPU-server-mirrored**, not locally re-runnable end-to-end; only the headline economic comparison is locally reproducible. State this explicitly as a reproducibility scope note.

**Copilot Opus reviewer gate:** ran read-only; outcome = **submittable with P1 fixes**. No files edited, no commands beyond read-only inspection. Remaining test gap: the PIT-inclusion backtest (P1-1) has not been executed — recommended before final submission.
