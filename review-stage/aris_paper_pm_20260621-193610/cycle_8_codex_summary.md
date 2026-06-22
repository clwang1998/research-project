# Cycle 8 Codex Summary

## Objective

Use the cycle-8 Copilot Opus quant-PM review to improve paper credibility,
especially horizon-transfer framing, survivorship interpretation, table
consistency, and deflation/overfit caveats.

## Implemented Fixes

- Ran a focused traded-horizon momentum IC robustness diagnostic for 5/10/20/30d
  sector-relative targets using existing cloud data and
  `scripts/build_momentum_ic_robustness.py`.
- Archived the compact 2022+ hold-out summary under
  `report/artifacts/momentum_ic_traded_horizons/`.
- Updated the report to state clearly that the strongest momentum confirmation
  is 1d cross-sectional IC, while the traded 20-30d implementation is
  positive but lower-power after HAC/block adjustment.
- Corrected `volume_z_20d` in the frequency table to the artifact value
  `0.514 / 1.93`.
- Reframed the survivorship haircut as an adverse sensitivity with unproven
  sign for a long-short momentum tilt, not a true correction.
- Clarified that CSCV PBO `50%` is an adverse but low-precision estimate over
  28 strategies and 20 splits.
- Removed misleading 30d bolding in the broad results table.

## Validation

- `git diff --check` passed.
- `python3 -m py_compile scripts/run_alpha_robustness_audit.py scripts/build_momentum_ic_robustness.py scripts/prepare_copilot_opus_review.py` passed.
- `pdflatex -interaction=nonstopmode -halt-on-error sp500_case_study.tex`
  passed twice from `report/`; final PDF is 10 pages.
- LaTeX log scan found no undefined references, overfull boxes, or material
  warnings beyond the normal `rerunfilecheck` package line.

## Commit / Push

- Local commit: `9f04400` (`Tighten ARIS paper horizon and survivorship framing`).
- Push attempted with `git push`; it failed because GitHub HTTPS credentials
  are not available in this noninteractive runtime:
  `fatal: could not read Username for 'https://github.com': terminal prompts disabled`.
- Push remains pending.

## Reviewer Gate

- Read and used
  `review-stage/20260621-212733-cycle8-quant-pm-copilot-opus.md`.
- Generated a narrow follow-up review prompt and placeholders:
  `review-stage/20260621-2138-round36-copilot-opus.md` and
  `review-stage/20260621-2138-round36-scope.md`.
- Follow-up Copilot Opus review could not run because the manual-review MCP
  tool is not exposed in this runtime and no VS Code Copilot browser handoff is
  available in the unattended cloud session.

## Remaining Risks

- Survivorship remains bounded, not corrected; point-in-time constituents and
  delisting returns are still required for production claims.
- The non-selected 30d LightGBM row still lacks an own archived DSR/PBO; the
  report rejects it through validation-selection discipline and the full-grid
  expected-max null.
