I'll start by exploring the repository structure and reading the key files in parallel.

Let me read the report in sections and explore the docs/output directories in parallel.

Let me continue reading the report and key docs in parallel.

Continuing to read the report's results/discussion sections and the audit docs.

Let me read the rest of the report (Results/Discussion) and remaining key docs.

Let me finish reading the report's discussion section and the report improvement plan.

Let me read the report's final sections and check key output summaries to verify numbers.

Now let me verify key numbers against output artifacts and check the PDF page count.

Let me verify the key momentum/Route B numbers from the JSON artifacts and get the PDF page count.

PDF is exactly 10 pages and momentum numbers match. Let me verify the Route B artifacts and robustness audit numbers referenced in the report.

Let me verify the Route B robustness audit numbers against the actual CSV/JSON artifacts.

Let me verify the remaining key artifacts (paired increment, IC robustness, traded horizons, PIT) and check prior review rounds.

Let me verify the remaining numeric artifacts and read the latest review round.

Let me verify the 5d/20d PIT haircut numbers (which underpin the abstract) and skim the latest review round.

All key numbers reconcile with artifacts. Let me confirm the mirrored prediction file exists locally (reproducibility) and that all figure references resolve.

I've inspected the report end-to-end and reconciled every headline number against the underlying artifacts. All key figures verify (momentum 5d/20d/30d Sharpes, DSR 0.003/0.814, PBO 50%, paired t=0.25, NW t=4.39, PIT haircuts), the PDF is exactly 10 pages, and all six figures resolve. Here is my read-only PM/senior-researcher review.

---

## Verdict
**No P0 blocker. No data-leakage, fabrication, or reproducibility break that invalidates a claim.** The numbers reconcile to the CSV/JSON artifacts, leakage controls are real and verified, and failed methods (graph/GAT/MLP/Kronos/seed-bag/Kaggle-agg) are honestly demoted. The paper is already above the average take-home bar on experimental hygiene. The remaining issues are **paper-credibility/framing**, not analytical errors — but for a *PM-pitch* deliverable they are submission-affecting, so I file them as P1.

---

## Blocker / priority findings

### P1-A — Showcase and space allocation contradict the stated recommendation (conviction optics)
- **Where:** §1 abstract endorses "**5-day sector-neutral momentum** … preferred" (tex 66–69), yet the two dedicated results tables (`tab:route_b_30d`, tex 618–648; `tab:p0audit`, tex 727–754) and ~3 prose blocks are the **30d Route B overlay**, while the abstract also leans on standalone **20d/30d** Sharpes (tex 86–91).
- **Impact on claim:** A PM cannot tell which single book you would run. You commit in one sentence (5d) but spend most evidence real-estate on a different horizon (30d) that you ultimately conclude is *indistinguishable from momentum* (paired t=0.25, 93% corr). It reads as "report whichever horizon flatters whichever metric."
- **Fix:** State one committed book once, with its full economics in a single block; relabel all other horizons explicitly as robustness/sensitivity. Make the committed-book row the bolded focal point of `tab:results`.

### P1-B — Load-bearing significance is at a horizon you do not trade
- **Where:** Headline leans on the **1-day** IC (plain t=3.54, NW-lag21 t=4.39; tex 82–83, `momentum_ic_robustness`). Traded-horizon block-bootstrap IC is t=2.41/2.13/1.89/1.85 at 5/10/20/30d, with **20d/30d CIs crossing zero** (`momentum_ic_traded_horizons`; tex 533–536).
- **Impact:** The strongest statistic (t=4.39) is non-decision-relevant because the recommended books trade ≥5d. A skeptical PM discounts it. The abstract currently leads with the 1d numbers.
- **Fix:** Foreground the **traded-horizon** evidence (5d t=2.41, IC CI [0.004, 0.042]) as the basis for the recommendation; demote 1d IC to a corroborating "signal-exists" clause.

### P1-C — After partial survivorship correction the endorsed book's net Sharpe CI includes zero, and this is never stated combined
- **Where:** PIT-inclusion cuts 5d momentum Sharpe 0.620→0.461, 20d 0.828→0.513, 30d 0.741→0.446 (`pit_inclusion_sensitivity*`; tex 931–934). The *un-haircut* 5d bootstrap CI is already [-0.32, 1.63] (`momentum_portfolio_uncertainty`). And PIT here is **inclusion-side only** — the harder short-side delisting returns are absent.
- **Impact:** The one signal you endorse has, after a partial and *optimistic* survivorship adjustment, a net-of-cost Sharpe (~0.46) whose interval comfortably includes zero. Each piece is disclosed, but the paper never states the combined implication, leaving the headline looking stronger than the portfolio evidence supports.
- **Fix:** Explicitly anchor conviction on **IC** (which survives the haircut far better — block-boot CI [0.0115, 0.0297]) and concede the portfolio Sharpe is **directional-only**. Report the PIT-filtered Sharpe *with* a CI, not just the point estimate.

### P2-A — Route B is over-featured relative to its evidential weight
Two tables + ~3 paragraphs for a result you conclude is a ~null increment (DSR 0.003, PBO 50%, IC gain negligible, paired t=0.25). For a 10-page PM artifact this buries the real lede (momentum is the only confirmed signal). Compress to one table + one paragraph; reclaim space for the committed book and survivorship quantification.

### P2-B — Multiple evaluators create small internal inconsistencies
20d momentum Sharpe appears as **0.82** (`tab:results`, 53 non-overlap periods) vs **0.83/0.828** (abstract/PIT, daily-overlap evaluator). Annualized return is arithmetic ×freq in `tab:route_b_30d` but geometric in `route_b_paired_increment`. `tab:results` rows mix IC (traded-horizon artifact) with Sharpe (portfolio-uncertainty evaluator). All footnoted, but the proliferation invites "which number is real?" Consolidate headline economics under **one** canonical evaluator; relegate alternates to an appendix.

### P2-C — Per-factor horizon selection is undercharged in the sleeve DSR
The frequency scan pre-registers 12 factors but selects each factor's native horizon by max|ICIR| over 6 horizons = **72 discovery cells** (tex 442–449), yet the sleeve DSR uses **N=12** (tex 483). The OOS confirmation mitigates this, but "momentum is the only survivor" is partly a max-over-horizons pick. Note the extra multiplicity or widen N for the single-factor DSR.

### P2-D — Selection-rule asymmetry invites a fair question
The unaudited 30d LightGBM beats momentum on **both** IC (0.036) and Sharpe (1.23) but is demoted for not being validation-selected, while the validation-selected 30d overlay (weaker increment) is showcased (tex 609–616, 842–845). The logic is correct; add a one-line explicit defense ("we credit no result outside the pre-committed validation rule, including ones that flatter us").

---

## Highest-ROI calculations (hours, current data, no retrain)
1. **Combined uncertainty for the committed book:** report the **PIT-filtered bootstrap Sharpe CI** (not just the 0.46 point estimate) so the reader sees whether it crosses zero — directly closes P1-C.
2. **Portfolio-level zero-alpha control:** a random-score sector-neutral L/S book under identical cost/turnover, giving the Sharpe numbers a null reference frame (you have IC-level random-graph controls but no Sharpe null).
3. **One consolidated "PM decision" block** for the committed book under a single evaluator: net Sharpe (raw / DSR-deflated / PIT-haircut), turnover, capacity at \$100M/\$1B, max DD, momentum correlation — the exact line §1 of the improvement plan asks for.
4. **Momentum IC half-life/decay curve** from the existing daily IC series to justify "low-turnover" and the horizon choice with a curve, not point picks.
5. **Recompute 20d Sharpe under the non-overlapping evaluator** to erase the 0.82/0.828 discrepancy.

---

## Wording / table / figure changes
- **Abstract:** lead with the committed book + traded-horizon evidence and the DSR-deflated, PIT-haircut net Sharpe; move t=4.39 to a corroborating clause; end with a one-sentence "what I'd trade, how much capital, next research dollar."
- **`tab:results`:** add an evaluator/units footnote per column, fix 20d Sharpe to one convention, bold the committed-book row.
- **Route B:** merge `tab:route_b_30d` and `tab:p0audit` (or appendix the latter); keep one headline line "overlay − momentum: t=0.25, not distinguishable."
- **Add three explicit sentences:** (a) the recommended book is X; (b) its portfolio Sharpe is directional-only, conviction rests on IC; (c) after partial survivorship correction the net Sharpe CI includes zero.

---

## Residual risks (non-blocking)
- **Reproducibility:** Route B XGBoost predictions were trained on a remote GPU and only *mirrored* locally; the overlay is re-evaluable from `predictions_val_test.parquet` and the momentum baseline reproduces exactly, but the model is not trainable from scratch in-repo. Disclosed — keep it disclosed.
- **Dividend adjustment** uncertainty (split-adjustment verified, dividends inferred) — correctly a minor caveat.
- **Single hold-out regime** (2022–2026, momentum-friendly): walk-forward folds touch 2008/2020, but the *endorsement* rests on one OOS window; the paper says so.

**Bottom line:** sound, honest, reproducible analysis; not a reject. The gap to a credible PM pitch is entirely **framing/conviction** (P1-A/B/C) — commit to one book, anchor conviction on IC not on the non-traded 1d t-stat or the survivorship-fragile Sharpe, and stop letting a null-increment overlay dominate the page budget.

