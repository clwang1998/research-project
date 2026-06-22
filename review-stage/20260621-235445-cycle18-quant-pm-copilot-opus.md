I'll review this as a read-only quant PM reviewer. Let me start by mapping the repository and reading the key files.

Let me read the report in sections and explore the directory structure in parallel.

Extensive prior review history. Let me continue reading the report body and the key docs in parallel.

The paper narrative is already quite disciplined. Let me read the rest of the report and key planning docs.

Let me read the rest of the report (Discussion/Conclusion) and the improvement plan.

Let me read the report's conclusion and the most recent review cycle to see what's already been flagged.

I have the full report and the most recent (cycle17) review. Now let me independently verify the headline numbers against artifacts and check the PDF page count, rather than trusting prior reviews.

PDF is 10 pages (meets limit). Let me independently verify the headline numbers against the artifacts.

Numbers reconcile well. Let me confirm the momentum baseline JSON structure and regime/PBO values.

Let me verify the regime Sharpe values and check what changed in the report after the last review cycle.

Regime numbers reconcile exactly (5d Sharpe −0.95/0.33/−0.14/0.62). Let me verify the capacity and factor-neutral claims, where I want to check the impact-model extrapolation.

All audit numbers reconcile cleanly. Let me confirm the traded-horizon IC claim (load-bearing for momentum) and glance at the route_b outputs.

I've independently verified every headline number against the artifacts. The traded-horizon IC (t=2.41/2.13/1.89/1.85; 20d/30d CIs cross zero), the 1-day IC (t=4.39, CI [0.0115,0.0297]), regime Sharpes (−0.95/0.33/−0.14/0.62), DSR (0.003/0.814), PBO 0.50, capacity, and survivorship all reconcile. PDF is 10 pages. Here is my review.

---

# Copilot Opus — Read-Only Quant PM / Senior Researcher Review
**Deliverable:** `report/sp500_case_study.tex` → `.pdf` (10 pages, meets ≤10). Supporting `docs/` + `output/` artifacts.

**Reproducibility (passed):** I recomputed/inspected the source artifacts, not just the prose. Momentum baselines (`output/momentum_baseline_priority/*.json`: 30d Sharpe 0.7403, ann 7.78%, DD −13.83%, turnover 0.401), Route B canonical IC (overlay 0.0279 vs momentum 0.0282), paired increment (t=0.248, corr 0.932, gap 0.246), DSR (0.003 @ N=884 / 0.814 @ N=14), PBO 0.50, FM t≈0.05, capacity, survivorship, cost-breakeven (gap≈0.25 to ~147 bps), and traded-horizon IC all match the paper. **No fabricated or unreproducible headline number.**

---

## Blocker findings

### P0 — none
There is **no blocking paper-level integrity defect.** No leakage, horizon-misalignment, sample-boundary, or overclaim that invalidates a headline. The paper is unusually honest: it does not claim ML beats momentum, frames Route B as drawdown-dampening not alpha, and demotes graph/GAT/MLP/Kronos/seed-bag correctly. If anything it *under*-claims. Remaining issues are judgment/framing.

### P1-A — The endorsed benchmark contradicts its own regime evidence (circularity)
- **Where:** §1 (l.66–73) and Conclusion (l.1052–1055) endorse "keep … the 5-day sector-neutral" momentum book as "the benchmark I would keep." §Discussion (l.1018–1019) + `momentum_regime_diagnostics.csv` show 5d Sharpe **−0.95 / +0.33 / −0.14 / +0.62** across 2008–11 / 2012–16 / 2017–21 / 2022–26. The *only* positive regime is the hold-out that produces every headline; the 2009 crash periods (−19.3%, −14.0%) are real.
- **Impact:** The standalone *portfolio* case is effectively fitted to the one momentum-friendly regime in the sample. PIT inclusion cuts 5d Sharpe 0.62→0.46 (CI [−0.49,1.43], crosses zero); mean-return t=1.31. A PM reads "I'd keep this book" against 3-of-4 negative slices as circular.
- **Fix:** Anchor conviction *explicitly* on IC + literature; state plainly the portfolio Sharpe is regime-confined to 2022–26. One sentence: "I size off IC stability and turnover, not this Sharpe, because the book only clears in the recent regime."

### P1-B — The load-bearing significance stat is at a non-traded horizon
- **Where:** The strongest number in the paper — NW lag-21 **t=4.39**, IC CI **[0.0115,0.0297]** (Table `tab:momentum_ladder`, l.847) — is a **1-day** IC (`momentum_ic_robustness`, `target_excess_sector_fwd_1d`). The tradable signal is 5–30d; `momentum_traded_horizon_ic_robustness.csv` confirms block-bootstrap IC **crosses zero at 20d (CI [−0.0013,0.063]) and 30d ([−0.0022,0.071])**, t falling 2.41→2.13→1.89→1.85.
- **Impact:** Momentum's "it exists / clearly survives" pillar (l.1051) rests on a horizon nobody trades at |IC|≈0.01, while the traded-horizon evidence is marginal. The Conclusion still leads with the 1d stat.
- **Fix:** Relabel the 1d row "signal existence (non-traded horizon)"; lead the Conclusion with the 5d *traded* t=2.41 and explicitly note 20d/30d cross zero. Drop "clearly" from "the one signal that clearly survives."

### P1-C — Self-defeating narrative undercuts the deliverable
- **Where:** Throughout §Results/§Discussion; this was the explicit target of `docs/report_improvement_plan.md §2.8`. Structure improved (headline-first §1, Route B as sleeve), but nearly every positive result is killed in the sentence it appears.
- **Impact:** For a take-home, risks reading as "candidate found nothing" rather than "candidate has the judgment to know what's real." Conviction is the stated gap and is still thin.
- **Fix (presentational):** Consolidate repeated kill-shots into one "Robustness verdict" box; lead each result with the *decision* it drives; end §1 with one unhedged sentence (what you'd paper-trade, at what capacity, the one experiment that flips the call).

### P2-A — Near-flat capacity curve is an out-of-range extrapolation *(new)*
- **Where:** `tab:p0audit` / §Discussion (l.998–1001) + `capacity_curve.csv`: Sharpe degrades only 0.97→0.86 from $10M→$1B. But the square-root impact model is **calibrated to 10 bps at 1% ADV**, while $1B p95 participation is **25.3%** — 25× past calibration, a regime where impact is super-linear and a 30-day long–short book simply cannot trade a quarter of ADV in the names.
- **Impact:** A skimming PM reads "$1B at Sharpe 0.86" as capacity being a non-issue; it is the opposite. The true ceiling is well below $1B.
- **Fix:** Cap participation (mark untradeable above ~10% ADV) or report the AUM at which p95 participation hits 10%, and label the high-AUM rows "extrapolated beyond calibration."

### P2-B — DSR verdict hinges on the trial count, and the dispersion is inflated
- `multiple_testing_dsr.csv`: same-target DSR **0.814** (N=14) vs full-grid **0.003** (N=884) — identical Sharpe/σ, only N differs. Paper now partly defends 884 (l.895–898), but `trial_sharpe_std=0.469` pools heterogeneous horizons/targets, which *mechanically inflates* expected-max-null (1.512) and pushes DSR down. So "fails DSR" is conservative; the honest read is "between 0.003 and 0.814," not a clean fail. **Fix:** report same-horizon N as primary, 884 as a conservative bound, and one line on the dispersion-pooling caveat.

### P2-C — Survivorship net-sign is asserted more firmly than the mechanism supports *(new nuance)*
- §Data (l.146–148) and §1 call the direction "optimistic/adverse" for the loser-short sleeve; §Discussion (l.977) correctly says "could affect either side." The inclusion side *is* empirically adverse (PIT cut 0.62→0.46). But the **deletion side cuts the other way**: absent bankrupt losers means the backtest *misses* the most profitable shorts → conservative on the short leg. **Fix:** settle on "net sign indeterminate" (inclusion-side adverse, deletion-side conservative) rather than "likely adverse," to avoid a reviewer catching the short-leg logic.

### P2-D — Two minor numeric hygiene items
- **Unlabeled stat:** l.620 "validation ICIR **0.0804** vs MLP's **0.4882**" is walk-forward *mean* val RankICIR — a different scale from the 0.7–1.2 ICIRs elsewhere; a reader can't reconcile it. Label the exact metric.
- **Annualization drift:** momentum 30d ann-return is **7.78%** (canonical JSON, Tables) vs **7.48%** (`route_b_paired_increment`, geometric @8.4/yr). Sharpe ties to 10 d.p., harmless, but state one convention.
- **Visual anchor:** the unaudited 30d LightGBM row (Sharpe 1.23/13.0%) is the most attractive cell in `tab:results`; already grayed+flagged, but consider an explicit "(not a result)" tag.

---

## Focused experiments that would most improve the report (each ≲ a few hours, current data only)
1. **CPCV / combinatorial-purged Sharpe distribution for the no-fit 5d momentum book** (highest ROI). The paper concedes "calendar slices, not CPCV proof" (l.1021). Momentum requires no fitting → recompute on every purged path → converts P1-A's four point estimates into a Sharpe distribution and directly answers "single lucky regime."
2. **Retrain the Route B residual model on ≥1–2 earlier walk-forward splits** to produce even a coarse 2008/2020 overlay Sharpe. The drawdown-dampening claim only matters in a stress regime and is currently never tested in one.
3. **Bootstrap CI on the canonical RankIC gap** (overlay − momentum, 0.0279 vs 0.0282). Turns "within evaluator noise" (l.605, l.40) into a number; trivial from existing predictions.
4. **Participation-capped capacity curve** (fixes P2-A): re-run with a 10%-ADV cap to expose the realistic capacity ceiling. One curve.

*(Note: the cost break-even experiment is already done — `route_b_cost_breakeven` shows gap≈0.25 to ~147 bps — so that prior ask is satisfied; don't re-request it.)*

## Wording / table / figure changes for the final report
- §1 + Conclusion: add one **conviction sentence** (what you'd paper-trade, sizing basis = IC stability not Sharpe, kill-criterion = PIT universe + CPCV); state the portfolio Sharpe is **regime-confined to 2022–26**.
- `tab:momentum_ladder`: relabel the 1-day NW-t row as **"signal existence (non-traded horizon)"**; drop "clearly survives" (l.1029, l.1051).
- Add one **"Robustness verdict"** box; remove per-paragraph re-hedging (P1-C).
- Capacity table: flag high-AUM rows **"extrapolated beyond calibration"** (P2-A).
- Soften survivorship to **"net sign indeterminate"** (P2-C); fix the **0.0804/0.4882** label and unify **7.78/7.48** (P2-D).

## Residual risks (acknowledged, not blocking)
- **N=35 non-overlapping periods** underlies every Route B economic claim — honestly disclosed but irreducibly thin.
- **Survivorship is inclusion-side only;** deletion side is parametric.
- **DSR family-size** remains a judgment call, not a theorem (paper says so).

---

**Bottom line:** Submit-ready on integrity and reproducibility; **not blocked by any P0.** The weaknesses are (1) a regime-confined portfolio behind the endorsed benchmark and (2) the strongest stat sitting at an untraded horizon (P1-A/P1-B), plus (3) a narrative that argues against itself (P1-C). Fixing those three — ideally backed by experiment #1 (CPCV) — moves this from "rigorous triage" to "credible PM-facing research."

**Reviewer-gate note:** I ran as the Copilot Opus read-only reviewer directly (the MCP browser handoff was not invoked). No files were edited; no commands beyond inspection were run. Outcome: **PASS with P1 framing fixes recommended, no P0 blockers.**

