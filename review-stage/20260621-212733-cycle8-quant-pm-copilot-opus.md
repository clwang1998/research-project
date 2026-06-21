I'll review this as a quant PM evaluating whether the paper is credible enough to submit. Let me start by mapping the repository and reading the key files.

Let me read the main report and key supporting docs in parallel.

The TeX file is large (953 lines). Let me read it in sections along with the key docs.

This is a deflation-first paper with a negative headline. Let me continue reading the report body and supporting audit docs.

Let me read the results and discussion sections of the report, plus the triage and improvement-plan docs.

Let me finish the report (results tables, discussion, conclusion) and read the improvement plan.

Let me read the final report sections (discussion, limitations, conclusion).

I've read the full report. Now let me verify internal consistency: page count, figure existence, and cross-check key numbers against the actual output artifacts.

All 6 figures exist. Let me check page count from the LaTeX log and verify key numbers against the artifact files.

Report is exactly 10 pages (meets limit), all figures present. Now let me verify the headline statistics against the underlying artifact CSVs to confirm the tables aren't fabricated.

The reported numbers match the artifacts precisely — paired increment (t=0.25, corr=0.93), momentum bootstrap (Sharpe 0.740, t=1.51), IC robustness (t=3.54, NW t=4.39), canonical IC, and sleeve-book DSR all reconcile. I found one small mismatch (volume_z disc ICIR: report 0.532 vs artifact 0.514). 

Let me now probe my strongest potential concern — the survivorship haircut's sign/mechanism — plus the leakage controls.

The leakage controls are rigorous and quantified. Now let me examine the survivorship haircut mechanism in the audit script — I want to verify the sign/economic logic of applying a haircut to the short side.

The leakage controls are rigorous and quantified. I found a substantive issue in the survivorship haircut. Let me do final checks: LaTeX warnings/undefined refs, and confirm the referenced output directories exist.

Build is clean (10 pages, no undefined refs, 0 overfull boxes), all output dirs exist, and the momentum baseline JSON matches the report exactly. Let me verify the final headline stats — DSR, PBO, and capacity — against the route_b audit CSVs.

All headline statistics reconcile exactly with the audit CSVs (full-grid DSR 0.003 at N=884, same-target DSR 0.814, PBO 50%, capacity 0.948/0.900/0.864, survivorship 0.951/0.837, FM t=0.048, factor-neutral return 8.27%→5.17%). The report is internally consistent, reproducible, within the 10-page limit, and figures all resolve.

I have enough to deliver the review.

---

# Copilot Opus — Read-Only Quant PM / Senior Researcher Review

**Verdict: No P0 blockers. The paper is submission-credible.** Numbers reconcile to artifacts, leakage controls are real and quantified, the page limit is met, and the headline is honest (deflation-first, negative). The issues below are P1/P2 refinements, not gates.

## Blocker triage

### P0 — none
I could not find a claim that materially overstates the evidence, a leakage path, or a table that contradicts its artifact. Every headline stat I spot-checked (paired t=0.25, corr 0.93; momentum bootstrap Sharpe 0.740/t=1.51/CI[-0.22,1.85]; IC t=3.54/NW-21 t=4.39; DSR 0.003/0.814; PBO 50%; capacity; survivorship; FM t=0.05) matches the CSV/JSON in `report/artifacts/` and `output/alpha_robustness_audit_route_b_30d/`.

### P1-1 — Horizon-transfer seam in the central claim (§1 lines 75–80; §6 Results 503–513; Table `frequency_confirm`)
The paper's load-bearing significance for momentum — plain `t=3.54`, NW-21 `t=4.39` — is a **1-day-forward** daily IC (`momentum_ic_robustness` is computed on `target_excess_sector_fwd_1d`, n=1115). But the entire deflation comparison and the recommended product are at **30d** (and 5/10/20d). At the traded 30d horizon, momentum's own rank-IC implies `t ≈ 1.4` (ICIR 0.698 over 35 non-overlap periods), mirroring the portfolio Sharpe `t=1.51`. So at the horizon you actually trade, *nothing — including momentum — is individually significant over this sample*.
- **Impact on claim:** A reader can mistake the 1d `t=3.54` for significance of the 30d book. The "momentum is the only confirmed factor" headline silently inherits 1d significance into a 30d conclusion.
- **Fix:** State explicitly that the daily (1d) IC is the cross-sectional *confirmation* while the 30d book is a thin-sample *implementation*; and report the momentum rank-IC t-stat (overlap-robust) at the 5/10/20/30d traded horizons so the seam is visible, not implied.

### P1-2 — Survivorship haircut sign is asserted, not justified (§2 lines 113–118; §8 Discussion 868–875; `scripts/run_alpha_robustness_audit.py:547–569`)
The haircut subtracts a uniform drag `0.5·rate·|loss|` and the prose attributes it to "short-side exposure." But losing money on a delisting requires being **long** the name. A 12–1 momentum book typically **shorts** declining/distressed names (Enron, Lehman fell before dying), where a delisting is a *profitable* short — i.e., survivorship bias for this specific long-short tilt is **directionally ambiguous**, not one-sidedly optimistic.
- **Impact on claim:** The "optimistically biased / haircut only lowers Sharpe" framing may have the wrong sign for the momentum leg; the bound is presented as conservative when it might be neither.
- **Fix:** Either justify the optimistic direction for the momentum tilt, or present a **two-sided** sensitivity (delisters as costly longs vs. profitable shorts) and correct the "short-side" labeling. Keep the "sensitivity, not correction" caveat.

### P2 — polish (none block submission)
- **Stale numbers, Table `frequency_confirm` (line 536):** `volume_z_20d` disc ICIR/t shown as 0.532/1.99; artifact `native_horizon_summary` says 0.514/1.93. Reconcile.
- **Mixed target families, Table `results` (lines 776–796):** 20d row is market-relative while 5d/30d are sector-relative. It's footnoted, but bolded "best" cells invite an apples-to-oranges cross-row read. Scope the bold to within-block, or add a sector-relative 20d row.
- **Plain LightGBM 30d row (Table `route_b_30d`, line 603; Sharpe 1.226 > overlay 0.987):** dismissed on "not val-selected + below null" grounds but has no **own** DSR/PBO. A skeptic fixates on the best point estimate. Give it a one-line DSR so the rejection is statistical, not procedural.
- **PBO = exactly 50.0%** over only 28 strategies / 20 splits: note CSCV instability at low strategy counts so 50% isn't read as a precise estimate.

## Highest-ROI experiments (hours, existing data only)
1. **Momentum IC t-stat at traded horizons (5/10/20/30d), overlap-robust NW** — reuse `build_momentum_ic_robustness.py` with longer-horizon targets. Closes P1-1; single biggest credibility gain. (~30 min)
2. **DSR for the plain LightGBM 30d row** — reuse the deflated-Sharpe machinery to kill the loose end symmetrically. (~30 min)
3. **Two-sided survivorship bound + `date_added` PIT-inclusion screen** — resolves P1-2 and turns the caveat into a defensible range. (~1–2 hr)
4. **Hold-out sub-period split (2022 / 2023–24 / 2025–26) of overlay vs momentum** — would show the vol/DD reduction is *stable*, letting you state the one real positive with more conviction. (~1 hr)

## Wording / table / figure changes
- **Abstract/§1:** add one clause that momentum's confirmation is the **daily** IC; the 30d book is thin-sample (already implied — make it explicit).
- **§1 / Conclusion:** state the *robust* positive more confidently — the overlay's vol 3.63%→2.89% and DD −13.8%→−7.3% are **not** deflated away (they're mechanical from 93% correlation + lower vol); frame it as a risk-sleeve win while keeping the "no significant return increment" caveat. The report currently under-sells its one durable result.
- **§2 / §8 survivorship:** relabel the haircut and state the sign assumption.
- **Table `frequency_confirm`:** fix `volume_z` numbers.
- **Table `results`:** make bold scoping unambiguous.

## Residual risks (acknowledge, don't fix)
Single favorable hold-out regime (2022–26 is momentum-friendly); style neutralization limited to price/volume+sector (no size/value/quality without fundamentals); survivorship is bounded, not corrected; N=35 non-overlapping periods is intrinsically low-power. All are already disclosed — none undermine the (appropriately humble) conclusion.

**Copilot Opus reviewer gate: ran (read-only, manual inspection of `report/`, `docs/`, `output/`, `scripts/`). Outcome: pass with P1/P2 refinements; no P0 blockers, no leakage or reproducibility breaks found.**

