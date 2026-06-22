Cycle 3 is complete.

Updated the paper/report to tighten the PM-facing claims around Route B:

- Added DSR trial counts, expected-max-null Sharpe, and explicit exploratory framing.
- Clarified overlay IC/ICIR as cross-convention and approximate.
- Made factor-neutral Sharpe interpretation evidence-based with return/turnover degradation.
- Explained the 20d market-relative table block.
- Compressed Kronos to future survivorship-bias/universe work only.
- Regenerated the tracked 9-page PDF.

Validation passed:

- `git diff --check`
- `pdflatex` twice from `report/`
- `python3`/`pypdf` confirmed `report/sp500_case_study.pdf: 9 pages`
- LaTeX log check found no overfull-box or unresolved-reference warnings

Cycle notes were written to:

- `review-stage/20260621-201250-cycle3-scope.md`
- `/root/research_project_aris/output/aris_paper_pm_20260621-193610/cycle_3_codex_summary.md`

Local commit created:

- `fb6e654 Tighten cycle 3 paper audit framing`

Push was attempted but failed because GitHub HTTPS credentials are unavailable in the unattended terminal: `could not read Username for 'https://github.com'`. The branch remains ahead locally, push pending.