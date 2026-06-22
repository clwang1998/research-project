I'll start by exploring the repository structure and reading the key files for this paper-level review.

Let me explore the directory structure and read the core files in parallel.

This is a long-running iterative research project (cycle 23). Let me read the main report and the key supporting docs.

The cycle23 placeholder is essentially empty. Let me read the main report TeX file in full (it's the primary deliverable).

The paper is carefully hedged. Let me continue reading the methodology, results, and discussion sections.

Let me read the rest of the paper - discussion, conclusion, and remaining sections.

I've read the full paper. Now let me verify key numbers against the supporting docs and artifacts in parallel.

Docs align with the paper. Let me read the triage and improvement plan, and verify the key output artifacts exist with matching numbers.

Docs are consistent with the paper. Now let me verify reproducibility: figure files, page count (10-page limit was flagged), referenced artifacts, and spot-check key JSON numbers.

PDF is exactly 10 pages, all figures present, momentum baseline reproduces exactly. Let me verify the most load-bearing statistics (the deflation/regime/PIT numbers) against their artifacts.

Let me read the CSV artifacts to verify the key statistics.

Numbers reproduce precisely against artifacts. Let me verify the DSR/PBO deflation figures and PIT sensitivity — the most consequential claims — then check the abstract for any overclaim.

Cost-breakeven reproduces (gap 0.246 at 5bps, ~147bps breakeven). Let me confirm the DSR/PBO/capacity audit figures, then I have enough to write the review.

Every load-bearing number reproduces exactly (DSR 0.003/0.814, PBO 50%, capacity 0.948/0.864, FM t=0.05). Let me glance at the most recent prior review cycle to calibrate and avoid repeating findings, then I'll write my independent review.

The cycle22 review found regime-circularity, buried headline, and self-negating tone. The current paper has clearly addressed much of that (answer-first paragraph added, IC-equality split test now done, conclusion reframed as "regime-contingent"). Let me verify a few NEW angles before writing — whether a passive yardstick, IC half-life, and the turnover-framing are consistent.

I've completed a full read-only inspection and verified every load-bearing number against `report/artifacts/` and `output/`. Here is my independent PM/senior-researcher review.

---

## Reviewer gate status
Copilot Opus reviewer **ran read-only** (no edits, no commits, no destructive commands). This is a direct repository inspection (MCP `manual_review` not invoked). Per the task's explicit "return findings only / do not edit files," I have **not** written to the cycle23 placeholder — findings are below for the orchestrator to archive.

**Verification done:** PDF compiles to exactly **10 pages** (meets limit); all 6 figures present; no undefined refs. Every headline stat reproduces from local artifacts: momentum 30d Sharpe 0.740/IC 0.0282; paired increment t=0.25, corr 0.93, gap 0.246; 1d IC plain t=3.54 / NW-21 t=4.39; 5d split-diff ΔIC 0.0168, CI [−0.0045,0.038], p=0.062; canonical overlay IC 0.0279; DSR 0.003 (N=884) / 0.814 (N=14); PBO 50%; capacity 0.948/0.864; FM t=0.05; regime Sharpes −0.95/0.33/−0.14/0.62. **All tie out.**

## Bottom line
**No P0 paper-killing blockers.** This is a rigorous, honestly under-claiming triage paper, and it has **materially improved since cycle22**: the answer-first paragraph now exists (§1), the 5d discovery-vs-holdout IC-equality test was added (the cycle22 ask), and the conclusion now calls momentum "regime-contingent" rather than "confirmed OOS." Residual issues are **conviction/framing plus two concrete, cheap gaps** — all P1/P2.

---

## Blocker findings

### P1-1 — The endorsement-vs-evidence gap on 5d momentum is now *disclosed* but not *resolved*, and its load-bearing pillar (1d IC) lacks the same regime test as 5d
**Where:** §1 "Answer first"/"Headline"; §Results signal-frequency + Table 5 (momentum ladder); §Discussion "Regime dependence"; Conclusion (lines ~1066–1078).
**Issue:** The one "kept" signal is 5d sector-neutral momentum, yet by the paper's own evidence: (a) its *traded-horizon* portfolio edge is positive only in the 2022–26 eval window (5d Sharpe −0.95 / 0.33 / −0.14 / 0.62 across regimes; 2008–11 mean-ret t=−1.90); (b) its only *statistically clean* evidence is the **1-day** IC (NW-21 t=4.39), a horizon never traded; and (c) the optimistic inclusion-side PIT filter alone cuts 5d Sharpe to 0.461 with CI [−0.49,1.43] crossing zero, while the likely-adverse delisting/short-leg effect is uncorrected. Critically, the discovery→holdout **1d IC triples (0.0066 → 0.0206)** — the same "OOS-stronger = regime flag" pattern — but the split-difference bootstrap was applied **only to the 5d series**, not to the 1d IC that the whole "signal exists" claim rests on.
**Impact on the claim:** "Momentum is the benchmark I would keep" is really "momentum is the least-rejected hypothesis, tradable-significant only in the test regime." The paper hovers between these two headlines.
**Fix:** (i) Run the discovery-vs-holdout IC-equality bootstrap on the **1d** series too (artifact already has both `mean_rank_ic` columns); report whether the 1d OOS strength is separable from zero. (ii) State the thesis as *regime-contingent benchmark, not a fundable edge* in one clean sentence and stop re-endorsing "keep the 5d book" in the next clause.

### P2-1 — Internal contradiction: 5d is called "low-turnover" while the paper documents it as the **highest** annualized-turnover horizon
**Where:** Conclusion line ~1068 ("cleanest **low-turnover** tradable-horizon stress") vs §1 line ~90 ("20d … **lower annualized turnover**") and Table 6 note line ~820 ("**1115%**/449%/337% for 5d/20d/30d").
**Issue:** 5d has the *lowest per-rebalance* turnover (0.22 vs ML's ~0.6) but by far the *highest annualized* turnover (1115%), which is the cost/borrow-relevant number for a PM. Using "low-turnover" as the stated reason to prefer 5d over 20d/30d cuts against the paper's own cost logic.
**Fix:** Qualify to "low *per-rebalance* turnover relative to the ML models" and justify the 5d-over-20d choice on **IC significance** (the only traded horizon with a positive lower IC bound), not turnover. 20d actually has higher Sharpe *and* lower annualized turnover — say so plainly.

### P2-2 — DSR emphasis + anchoring rows still over-signal one direction
**Where:** §Discussion "Multiple testing"; Tables 2 & 6.
**Issue:** The headline leans on full-grid **DSR 0.003**, which the text itself admits pools 884 heterogeneous trials (a loose, inflated bound). Meanwhile val-rejected LightGBM (Sharpe **1.23**) and diagnostic λ=0.3 (**1.20**) sit un-greyed in the tables; a skimming PM anchors on them.
**Fix:** Lead with "overlay **fails 0.95 under any trial count** (0.814 same-target, 0.003 full-grid)" and de-emphasize the precise-looking 0.003; grey/footnote the two non-selected high-Sharpe rows.

---

## Highest-ROI experiments (hours, existing data only)
1. **1d IC discovery-vs-holdout split-difference bootstrap** — the single most important add: it stress-tests the paper's *only* statistically clean pillar. You already built the 5d version; reuse it on the 1d series in `momentum_ic_robustness/`. If the 1d gap also straddles zero, the honest headline becomes "even signal-existence is regime-contingent."
2. **IC decay / half-life curve** across the existing horizon grid — directly justifies endorsing 5d when significance lives at 1d and tradability fades by 20–30d. Currently absent; resolves the 1d-vs-traded-horizon gap a PM will probe.
3. **Passive / zero-skill yardstick** — add an equal-weight or random-sector-neutral reference Sharpe so 0.62 has a frame (cycle22 ask, still not done; cheap).
4. **Pooled pre-2022 IC t-stat (one number)** from the four `momentum_regime_diagnostics/` slices — converts "adverse in 2008–11/2017–21" from scattered cells into a single regime-robustness statistic.

## Wording / table / figure changes
- Fix the "low-turnover" contradiction (P2-1) in the Conclusion and §1.
- One clean thesis sentence: *regime-contingent benchmark, not a fundable standalone edge*; stop re-endorsing in the adjacent clause.
- Add capacity ($100M Sharpe 0.948) and corr-to-momentum (0.93) into the answer-first paragraph so page 1 is fully self-contained.
- Lead the DSR sentence with "fails 0.95 under any N"; grey out val-rejected LightGBM and λ=0.3 rows.
- Soften Table 4's "Positive OOS" read-through with the "3× discovery, may be regime luck" caveat.

## Residual risks (disclosed, not blocking)
- **Leakage controls rest partly on un-audited reruns** (`docs/data_leakage_review.md` notes purge/embargo fixes still need script-diff verification). The "controls bind / no-embargo inflates" claim is reasonable but not independently re-audited here.
- **Survivorship sign is genuinely unidentified and likely adverse** for a momentum book (missing delisted losers belong in the short leg); only inclusion-side PIT + parametric haircut available. PIT-filtered 5d Sharpe 0.461 (CI crosses zero) is the correct, prominent "not fundable yet" anchor — keep it.
- **Dividend-adjustment** uncertainty (minor, disclosed).

**Net:** Submission-credible and clearly above a median take-home on rigor. The remaining gap to a *convincing* PM artifact is conviction discipline (P1-1) and two cheap quantifications (experiments 1–2), not methodology or reproducibility.

