# Cycle 9 Codex Summary

## Objective

Improve the final ARIS quant research report using the cycle 9 Copilot Opus
paper-first review, with priority on survivorship, claim discipline, and
PM-level credibility.

## Implemented

- Added a focused PIT inclusion sensitivity builder:
  `scripts/build_pit_inclusion_sensitivity.py`.
- Generated `report/artifacts/pit_inclusion_sensitivity/`:
  summary CSV, current-membership and PIT-filtered backtest streams, README, and
  run metadata.
- Updated `report/sp500_case_study.tex` and rebuilt the PDF:
  - decision-first headline language;
  - PIT inclusion sensitivity in the P0 robustness table and survivorship
    discussion;
  - explicit distinction between PIT inclusion sensitivity and delisting-haircut
    stress;
  - added annualization, DSR pooling, and 2008 warm-up caveats.

## Key Result

Using `sp500_member_asof == 1` materially weakens the 2022--2026 point estimates:

| Signal | Current-membership Sharpe | PIT-inclusion Sharpe | Annual return delta |
| --- | ---: | ---: | ---: |
| 30d momentum | 0.741 | 0.446 | 7.79% -> 3.91% |
| Route B overlay | 0.987 | 0.725 | 8.27% -> 5.69% |

This supports the paper's conservative conclusion: momentum remains the core
benchmark, Route B remains exploratory, and true point-in-time constituents plus
delisting returns are required before any production claim.

## Validation

- `python3 -m py_compile scripts/build_pit_inclusion_sensitivity.py scripts/eval_momentum_baseline.py scripts/run_alpha_robustness_audit.py scripts/run_model_pipeline.py`
- `python3 scripts/build_pit_inclusion_sensitivity.py`
- `pdflatex -interaction=nonstopmode -halt-on-error sp500_case_study.tex` twice
  from `report/`; output remains 10 pages.
- `git diff --check`

`pdfinfo` and `pdftotext` are unavailable in this runtime.

## Reviewer Gate

The input Copilot Opus quant-PM review was read first from
`review-stage/20260621-214109-cycle9-quant-pm-copilot-opus.md`. A post-fix Opus
rerun could not be performed because `mcp__manual_review__review` is not exposed
in this runtime and there is no unattended interactive Copilot handoff.

## Commit / Push

- Local commit: `6f030bb Add PIT inclusion sensitivity to ARIS paper cycle 9`.
- `git push` failed because GitHub HTTPS credentials are unavailable in the
  noninteractive terminal. Push is pending.
