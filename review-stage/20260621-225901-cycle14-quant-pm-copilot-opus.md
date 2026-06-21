I'll start by exploring the repository structure and reading the key files to perform a thorough paper-level review.

Now let me read the main report and key supporting docs. The .tex is large, so I'll read it in sections.

Let me continue reading the report and the triage/improvement docs in parallel.

Let me continue reading the report's methodology, results, and discussion sections.

I've read the full report. Now let me review the improvement plan, reviewer doc, and the actual output artifacts to verify the numbers.

Let me verify the key numbers against the actual artifact files.

The momentum numbers match. Let me verify the critical Route B and IC robustness artifacts that anchor the headline claims.

Let me verify the traded-horizon IC and daily IC robustness artifacts — these now anchor the headline benchmark claim.

All numbers verify cleanly. Let me check the figures, the DSR/PBO audit source, and the factor sleeve book to complete verification.

Let me verify the DSR/PBO/Fama-MacBeth source numbers for the P0 audit table.

Let me confirm the PDF page count (the improvement plan flagged a 10-page limit) and check the conversation notes for the stated deliverable constraints.

Let me quickly check the review-stage placeholder and the take-home framing to calibrate the review bar.

I've completed a full read of the report, all supporting docs, and verified every headline statistic against the source artifacts. All numbers reconcile, the failed methods (graph/GAT/Kronos/MLP) are honestly demoted, the PDF is exactly 10 pages with no broken refs, and the traded-horizon IC backbone is genuinely on the 2022+ hold-out. Findings below.

---

## Reviewer verdict: no blocking (P0) paper-level issue

The central claim is appropriately hedged and the evidence supports it. The paper does *not* overclaim alpha: it argues 12–1 momentum is the only defensible benchmark, that ML/graph/MLP add no statistically robust increment, and that better data is the next dollar. Numbers are traceable and internally consistent. This is a credible research-judgment artifact. The issues below are **strengthening (P1) and polish (P2)**, not corrections.

---

## P1 — material, would change a PM's read

**P1-1 · Short-side borrow/financing cost is omitted from an all-long–short paper.**
- *Where:* §Methodology "Portfolio and metrics" (L432–436), §Discussion "Turnover, capacity" (L977–985), all of Tables `tab:results`/`tab:route_b_30d`. Only 5 bps/side trading + sqrt-impact is charged; no stock-borrow on the short leg.
- *Impact:* Every net Sharpe in the paper (0.62 / 0.74 / 0.99) is the *gross-of-borrow* number. Momentum shorts are prior losers — exactly the hard-to-borrow names. This systematically flatters the headline book the paper recommends.
- *Fix:* Add a borrow haircut sensitivity (25/50/100 bps annualized on the short notional) to the 5d/20d/30d momentum books and the overlay; or, at minimum, a one-line caption stating borrow is excluded. ~1 hour, existing return streams in `report/artifacts/*returns.csv`.

**P1-2 · The rigorous statistical audit sits on the thinnest sample (N=35), while the actual recommendation (5d, N=220) is never given the same treatment.**
- *Where:* `tab:p0audit` / `tab:route_b_30d` run DSR/PBO/Fama–MacBeth on the **30d** overlay (N=35 non-overlap; PBO=20 splits×28 strategies; FM=35 dates). The endorsed benchmark is **5d** (N=220), which only gets a bootstrap CI.
- *Impact:* At N=35 none of DSR/PBO/FM have power — the 9-row audit table implies more rigor than 35 observations can carry, and the book you'd actually trade (5d) is never deflated for the 12-signal×6-horizon search.
- *Fix:* Re-run the DSR/PBO/bootstrap audit at 5d/10d (`scripts/...` already parameterized by horizon) so the headline benchmark carries a properly deflated significance statement.

**P1-3 · Asymmetric multiple-testing treatment (heavy deflation on what you kill, light on what you keep).**
- *Where:* Overlay charged 884-trial full-grid DSR (L883–890); momentum IC t=2.41/3.54 (L88, L541–548) defended only informally as "only survivor."
- *Impact:* A sharp PM reads this as convenient. It's actually defensible — momentum's 1d native horizon was discovery-selected and OOS-confirmed (verified: traded-horizon CSV is 2022+ hold-out) — but the paper doesn't make that principle explicit.
- *Fix:* State plainly that momentum's IC is exempt from in-sample-max deflation *because* it is a pre-registered discovery→hold-out survivor, and add a Bonferroni/DSR-on-IC line for the 12-signal scan to close the loop symmetrically.

**P1-4 · Survivorship sign is framed as fully "unidentified," which under-commits.**
- *Where:* L131–140, L936–963. The PIT filter only removes recently-*added* names (inclusion side); truly delisted names are absent from the whole panel and cannot be restored.
- *Impact:* "Could affect either side" is technically true but evasive. The literature direction (delisting losers concentrate on the short side) is informative and should be stated rather than left agnostic.
- *Fix:* Cite the expected direction and label the current estimate as *likely optimistic*; keep the parametric delisting haircut but apply it asymmetrically (loser-heavy short leg) as a directional bound.

**P1-5 · Two evaluators give different momentum Sharpe; paper claims "one canonical evaluator."**
- *Where:* 5d Sharpe = **0.627** (`momentum_excess_sector_5d...json`, `momentum_portfolio_uncertainty.csv`) vs **0.620** (`pit_inclusion_sensitivity_5d`); 20d **0.822** vs **0.828**. Report quotes 0.620/0.828 in PIT context and 0.63/0.82 elsewhere (L70, L92, L1022 vs L843, L848).
- *Impact:* Small (~0.006) but it undercuts the explicit "one canonical portfolio evaluator" claim (L909–913, L1042).
- *Fix:* Footnote the ~0.006 gap (date-count/universe handling) or route both through one evaluator.

---

## P2 — polish

- **P2-1 Annualization:** returns are arithmetic mean × rebalances/yr (overstates vs geometric, esp. 30d×8.4). Disclosed (L641) but headline should prefer geometric or show both.
- **P2-2 Overlay "risk-timing sleeve" slightly overclaims:** the Sharpe-gap CI is [−0.17, 0.63] (verified, crosses zero), so even the *risk-dampening* is not statistically established — only the point estimate. Soften L678/L1005.
- **P2-3 Factor-neutral confusion:** neutralized overlay keeps Sharpe ≈1.0 *while* FM t=0.05 (L754–755, L924–929). Explain why a momentum-neutralized book stays momentum-like (score-level vs return-level neutralization), or a reader infers residual alpha.
- **P2-4 5d-over-20d choice:** you keep the *lower*-Sharpe 5d (0.62) over higher-Sharpe 20d (0.83). The justification (tighter IC CI from more non-overlap samples + lower turnover) is sound but is a risk-preference, not a dominance — state it as such, since another PM could rationally pick 20d.

---

## Focused experiments that would most improve the report (each ≤ a few hours)

1. **Short-side borrow sensitivity** (P1-1) — re-deduct 25/50/100 bps annualized on short notional across the 5d/20d/30d books + overlay. Highest ROI; closes the most obvious PM objection.
2. **Move the DSR/PBO/bootstrap audit to 5d/10d** (P1-2) — give the *recommended* book a deflated significance statement where N actually supports it.
3. **Deflate the momentum IC for the 12×6 frequency scan** (P1-3) — a 10-minute Bonferroni/DSR-on-IC line makes the multiple-testing treatment symmetric and pre-empts "you mined momentum."
4. **Asymmetric (loser-weighted) delisting bound** (P1-4) — reuse the existing parametric haircut on the short leg only for a directional, not agnostic, survivorship statement.
5. **Geometric vs arithmetic reconciliation** for the four headline books — quick, removes a credibility nick.

---

## Wording / table / figure changes for the final report

- **Lead the abstract with the one clean positive result** before the hedges: *12–1 momentum has a positive, OOS-confirmed cross-sectional IC at 5–10d (5d block-bootstrap t=2.41, CI [0.004,0.042]; 1d daily t=3.54, NW-lag21 t=4.39) at the lowest turnover.* Right now the reader must mine three dense paragraphs to extract a claim; the strongest, cleanest finding is buried under CIs that cross zero.
- **Every net-Sharpe table caption** (`tab:results`, `tab:route_b_30d`): state "net of 5 bps/side trading cost; **stock-borrow excluded**" until P1-1 is done.
- **`tab:p0audit` title:** foreground "**N=35 non-overlapping periods — tests are low-power**" and relabel FM/PBO rows accordingly so the table doesn't imply settled rigor.
- **Footnote the 0.620/0.627 and 0.822/0.828** momentum-Sharpe pairs (P1-5).
- **Soften L678 / L1005** "candidate risk-timing sleeve" → "point-estimate volatility/drawdown reduction, not statistically distinguishable (Sharpe-gap CI crosses zero)."
- Figures: all six referenced figures exist and resolve; no mismatch found. No action needed.

---

## Residual risks (since no P0)

1. **Single macro regime.** All hold-out Sharpes come from one continuous 2022–2026 block; the "momentum is the benchmark" conclusion is regime-conditioned despite the walk-forward stability figure.
2. **Survivorship remains uncorrectable in-scope** — the paper's own (correct) position. The book is therefore a research benchmark, not production evidence, and the paper should never be read as a trade-ready claim.
3. **Borrow costs (P1-1)** until added, all net figures are upper bounds.
4. **N=35 false precision** at 30d — the elaborate audit there is directional, not conclusive.

**Bottom line:** A rigorous, honest, well-sourced triage paper that correctly refuses to overclaim. The failed methods are demoted truthfully and the headline survives scrutiny. The fastest credibility gains are borrow costs, running the robustness audit where N is adequate (5d/10d), and symmetric multiple-testing language — none of which threaten the conclusion, all of which harden it.

*(Read-only review — no files edited, no commands beyond inspection. Note: the Copilot Opus reviewer-MCP gate in AGENTS.md was not invoked; this review was produced directly by the Opus reviewer against the worktree.)*
