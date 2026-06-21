I'll start by exploring the repository structure and reading the key files in parallel.

Strong context so far. Let me read the main report and remaining docs in parallel.

Now let me read the main report itself — the key deliverable. Let me check its size and structure first.

The report is the key deliverable. Let me read it in full, in sections.

I've read the full report. Now let me verify key claims against the actual artifacts and check page count and figures.

PDF is exactly 10 pages (at limit), and 30d momentum numbers match artifacts. Let me verify the other key artifacts.

All numbers verified against artifacts so far. Let me check the robustness audit (DSR/PBO trial counts) and the IC robustness artifacts.

Audit numbers all match. Let me verify the factor-neutral, Fama-MacBeth, capacity, and traded-horizon artifacts.

Excellent — every number reproduces against artifacts. Let me confirm the feasibility of my top recommendation (PIT haircut for the endorsed 5d signal) by checking the scripts and PIT machinery.

I have now verified every headline number against the underlying artifacts and confirmed the PIT machinery is horizon-parametrized. Here is my review.

---

## Copilot Opus (read-only) paper review — `report/sp500_case_study.tex`

**Gate status:** This is the Opus read-only reviewer round. I inspected the repo directly, did not edit/run/commit, and verified claims by reading artifacts only. **Verification: all headline numbers reproduce exactly** — 30d momentum (0.740 Sharpe / 0.0282 IC / 0.401 turn), 5d (0.627/0.0234/0.22), 20d (0.822), paired increment (t=0.25, corr 0.93, gap CI [-0.17,0.63]), DSR full-grid 0.003 over N=884, same-target 0.814 over 14, PBO 50% (28 strat/20 splits), factor-neutral 1.006/FM t=0.05, capacity, survivorship, daily IC (plain t=3.54, NW-21 t=4.39, CI [0.0115,0.0297]), traded-horizon block-boot t (2.41/2.13/1.89/1.85), PIT 0.741→0.446. PDF = 10 pages (at limit).

### Blocker findings

**No P0.** The paper is deflation-first and does not overclaim; I found no leakage error, no unsupported headline, no reproducibility break. The residual-target construction (per-date cross-sectional residualization of the forward label) is standard and not look-ahead. State this explicitly: the submission is methodologically clean.

**P1-A — Endorsed signal's survivorship risk is quantified at the wrong horizon.** §1/§Conclusion endorse **5-day** sector-neutral momentum (Sharpe 0.63, turnover 0.22) as the tradable benchmark, but the only PIT inclusion haircut computed is **30-day** (0.741→0.446, a 40% cut), then used to caveat the 5d call. The single largest risk in this current-membership dataset is left un-quantified for the actual recommendation. *Impact:* the headline conviction rests on an un-stress-tested horizon; the true 5d net-of-inclusion-bias Sharpe could be ≈0.4. *Fix:* `scripts/build_pit_inclusion_sensitivity.py` is horizon-parametrized (`--horizon-days 5 --target-col target_excess_sector_fwd_5d --return-col target_ret_fwd_5d`); run it for 5d/20d momentum and report those haircuts next to the endorsement.

**P1-B — The abstract buries the lede and self-negates.** §1 is a ~60-line wall containing 8+ Sharpe values, 6 t-stats and 5 CIs across three horizons plus the overlay. The improvement plan explicitly warned about inverted signal-to-noise ("叙事自我证伪"). *Impact:* a PM cannot extract the decision; the report reads as "I built nothing," undercutting the conviction the rewrite was meant to add. *Fix:* compress §1 to ≤5 sentences — (1) what I'd trade/benchmark, (2) one net Sharpe + its honest CI, (3) the survivorship haircut, (4) ML verdict in one line, (5) next research dollar. Move the horizon-by-horizon t-stat catalog into Results.

**P1-C — "No construction produces statistically deflated alpha" is asserted, not demonstrated, for the best raw performer.** In both Table `tab:results` and `tab:route_b_30d` the plain 30d **LightGBM** has the table's highest Rank IC (0.036), highest Sharpe (1.23), highest return (13.0%) — beating momentum and the featured overlay on every axis. It is removed *only* by the validation-ICIR rule (val ICIR 0.080 vs MLP 0.488) "before deflation," and the rule provably selects the worse hold-out model (MLP 0.69 Sharpe). *Impact:* the central negative headline can look like selection-rule convenience rather than evidence; a skeptical PM will ask whether the rule was reverse-engineered to make momentum win. *Fix:* run DSR/PBO on the LightGBM row too (`scripts/run_alpha_robustness_audit.py` pointed at its run dir) so "nothing survives deflation" is literally shown, **or** soften the blanket claim to "no construction has *demonstrated* deflated alpha."

**P2 (precision):**
- Factor-neutral Sharpe (1.006) is *higher* than raw (0.987), which naively reads as "alpha survived," yet is used in the bear case. Add one sentence: the FM marginal coefficient (t=0.05) is the decisive orthogonality test; the neutralized book's Sharpe is mechanically similar because the residual is still a higher-turnover momentum tilt.
- `tab:results` 20d: Ridge (0.83 Sharpe, 9.0% ann) edges the **bolded** momentum (0.82, 7.8%); bolding obscures a benchmark-beating model. Re-caption or footnote so the claim "momentum beats every trained model" isn't contradicted by the row directly beneath it.
- Overlay Rank IC is **negative** under the residual-label convention (−0.0083 vs canonical +0.0279). Disclosed but under-explained — state plainly that the residual score does not even rank its own residual label positively OOS, reinforcing FM t≈0.
- Survivorship sign is called "unidentified" in §Data but 0.446 is elevated to "the number a PM should keep in mind" in §Conclusion — reconcile (it is one directional sensitivity, not a bound).
- Minor: momentum Sharpe printed as both 0.740 and 0.741; "only traded row with a positive IC interval" — 10d's interval is also positive ([0.0016,0.050]).

### Highest-ROI experiments (each ≲ a few hours, machinery already exists)

1. **PIT 5d/20d momentum haircut** (P1-A). One command per horizon; directly hardens the headline. Highest impact.
2. **DSR/PBO on the plain 30d LightGBM** (P1-C). Converts "excluded by rule" into "demonstrably fails deflation," removing the strongest line of PM skepticism against the negative headline.
3. **Inclusion-side PIT as an interval, not a point.** You already have low/base/stress delisting; combine with the inclusion filter to report a survivorship Sharpe *range* for the endorsed book rather than a single 0.446.

*(Lower priority / out of cheap scope: a 5d/20d residual overlay needs new short-horizon prediction files — more than a few hours; note it as future work rather than attempting it.)*

### Wording / table / figure changes for the final report

- Rewrite §1 as decision-first (P1-B); relocate the horizon t-stat catalog to Results.
- `tab:results`: add a "PIT-inclusion Sharpe" column (once computed); fix the 20d bolding; add one provenance note for the mixed-source 20d row (IC/ICIR from traded-horizon artifact, economics from the canonical evaluator).
- `tab:route_b_30d`: give the "Plain LightGBM" row a DSR/PBO cell (even "n/a, not val-selected") or demote it to prose, so it isn't read as a fair, deflated comparator.
- Add the one-sentence factor-neutral reconciliation; tidy the 0.740/0.741 and "only traded row" wording.

### Residual risks (with no P0)
- The negative headline leans on a DSR the report itself calls "conservative, not a clean family-wise theorem" (N=884 pools heterogeneous horizons) — fine because it errs conservative, but the asymmetry (rigorous self-deflation vs. an admittedly-imperfect statistic) should be acknowledged in one line.
- The endorsed 5d book's own portfolio Sharpe CI crosses zero ([-0.32,1.63]); the endorsement is correctly IC-and-turnover-based, but that means the deliverable is "trade a signal whose tradable Sharpe is statistically indistinguishable from zero." State it as a deliberate conviction call, not a hedge.
- Entire model comparison rides on a validation-ICIR rule shown to pick the worse hold-out model — defensible as anti-peeking pre-registration, but say so explicitly rather than by implication.

Net: a strong, honest **triage/rejection** study with no submission-blocking errors. Closing P1-A and P1-C, and tightening the abstract (P1-B), is what moves it from "rigorous methodologist" to "PM-ready conviction."

