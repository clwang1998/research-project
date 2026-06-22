# Cycle 21 Codex Summary

## Changes

- Addressed the cycle 21 Copilot Opus quant-PM review in
  `report/sp500_case_study.tex`.
- Reframed the headline so 1d discovery/confirmation IC supports signal
  existence, while the 5d traded-horizon `t=2.41` is explicitly
  regime-contingent.
- Promoted PIT inclusion sensitivity as the binding funding blocker for the
  endorsed 5d book: Sharpe `0.620 -> 0.461`, CI `[-0.49, 1.43]`.
- Added a rough four-horizon selection haircut for the archived
  sector-relative traded-horizon scan: raw `p=0.0087` becomes about `0.035`.
- Added a Route B IC-convention signpost and removed grey emphasis from
  non-result 30d LightGBM diagnostic rows.
- Regenerated `report/sp500_case_study.pdf`; final compile reports 10 pages.

## Validation

- `git diff --check` passed.
- LaTeX compiled twice with `pdflatex`; final log:
  `Output written on sp500_case_study.pdf (10 pages, 745609 bytes).`
- Python compile was not applicable because no Python scripts were touched.

## Reviewer Gate

- Used the provided read-only Copilot Opus review:
  `review-stage/20260622-003717-cycle21-quant-pm-copilot-opus.md`.
- No second Opus round was run after these edits.

## Commit / Push

- Local commit created with message:
  `Tighten ARIS paper regime and survivorship claims`.
- Push was attempted but failed because GitHub HTTPS credentials were unavailable
  in the unattended runtime; push remains pending.

## Remaining Gaps

- No true PIT constituent universe or delisting-return correction is available.
- The 5d momentum portfolio remains a research benchmark, not fundable alpha:
  tradable-horizon significance is concentrated in 2022--2026 and the
  inclusion-side PIT Sharpe interval crosses zero.
