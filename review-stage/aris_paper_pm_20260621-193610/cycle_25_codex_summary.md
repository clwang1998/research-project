# Cycle 25 Codex Summary

## Objective

Address the cycle 25 paper-first Copilot Opus review, prioritizing claim discipline and the missing endorsed-horizon Route B audit.

## Changes

- Added and ran `scripts/build_route_b_5d_overlay_audit.py`.
  - Validation selected Route B lambda 1.0 at the 5d horizon.
  - 2022--2026 hold-out: momentum Sharpe 0.627, 5d overlay Sharpe 0.713, annual return 5.92% -> 5.15%, max drawdown -14.60% -> -11.79%, turnover 0.221 -> 0.481.
  - Paired return increment is not positive: t=-0.27, overlay/momentum correlation 0.78, paired Sharpe-gap CI [-0.55, 0.77].
  - DSR is effectively zero under same-target and full-grid trial counts.
- Recomputed canonical raw-label 5d Route B IC under `report/artifacts/route_b_5d_canonical_ic/`.
  - 5d overlay raw Rank IC is 0.019 versus momentum 0.023.
- Added `scripts/build_momentum_ic_decay_figure.py` and `report/figures/fig_momentum_ic_decay.pdf`.
  - The report now addresses the 1d-vs-5d horizon question with a traded-horizon IC-decay figure.
- Updated `report/sp500_case_study.tex` and rebuilt `report/sp500_case_study.pdf`.
  - Route B is now led by the horizon-matched 5d audit.
  - The old 30d overlay is demoted to sensitivity evidence.
  - The conclusion no longer frames the 5d overlay audit as future work.

## Validation

- `python3 scripts/build_route_b_5d_overlay_audit.py`
- `python3 scripts/build_route_b_canonical_ic.py --prediction-path output/model_search/route_b_factor_residual_alpha_core_20260622__target_excess_sector_fwd_5d__tabular__xgboost__xgb_balanced/predictions_val_test.parquet --overlay-lambda 1.0 --horizon-days 5 --out-dir report/artifacts/route_b_5d_canonical_ic`
- `python3 scripts/build_momentum_ic_decay_figure.py`
- `python3 -m py_compile scripts/build_route_b_5d_overlay_audit.py scripts/build_momentum_ic_decay_figure.py`
- `pdflatex -interaction=nonstopmode -halt-on-error sp500_case_study.tex` twice from `report/`
- `git diff --check`

The final LaTeX build is 10 pages with no undefined-reference or error warnings found in the log scan.

## Reviewer Gate

Read the supplied cycle 25 Copilot Opus paper review at `review-stage/20260622-013231-cycle25-quant-pm-copilot-opus.md`. No new Copilot Opus re-review was run in this runtime because the manual-review MCP tool is not exposed here.

## Commit / Push

- Local commit: `Cycle 25 tighten Route B paper claims`
- Push attempted, but HTTPS credentials were unavailable in the non-interactive runtime: `fatal: could not read Username for 'https://github.com': terminal prompts disabled`.
- Push is pending.
