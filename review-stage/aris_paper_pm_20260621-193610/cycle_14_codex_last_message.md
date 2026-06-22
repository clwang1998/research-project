Cycle 14 is complete.

Implemented the paper-level fixes from the supplied Copilot Opus PM review:

- Added reproducible borrow-cost sensitivity via `scripts/build_borrow_sensitivity.py`.
- Generated `report/artifacts/borrow_sensitivity/`.
- Updated `report/sp500_case_study.tex` and rebuilt the 10-page PDF.
- Tightened claims around borrow exclusion, survivorship direction, multiple testing, PIT-vs-canonical Sharpe consistency, and Route B’s exploratory sleeve framing.
- Saved scope notes in `review-stage/20260621-225901-cycle14-scope.md`.
- Wrote the requested summary at `output/aris_paper_pm_20260621-193610/cycle_14_codex_summary.md`.

Validation run:

- `python3 scripts/build_borrow_sensitivity.py`
- `python3 -m py_compile scripts/build_borrow_sensitivity.py`
- `git diff --check`
- `pdflatex -interaction=nonstopmode -halt-on-error sp500_case_study.tex`
- Final LaTeX log reports `sp500_case_study.pdf (10 pages, 742473 bytes)`.

Local commit created:

`5e09e9f Tighten ARIS paper borrow and survivorship caveats`

Push was attempted but failed because HTTPS credentials are unavailable in this non-interactive runtime:

`fatal: could not read Username for 'https://github.com': terminal prompts disabled`

Copilot Opus: used the provided read-only review file. A fresh post-fix manual-review MCP handoff could not run because `mcp__manual_review__review` was not exposed, and deferred tool discovery did not expose a manual-review equivalent.