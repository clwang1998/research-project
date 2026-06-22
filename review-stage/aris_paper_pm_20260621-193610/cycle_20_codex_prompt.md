You are Codex running unattended on the cloud GPU server for an 8-hour ARIS paper-iteration loop.

Repository: /root/research_project_aris
Branch: codex/supervised-gat-ensemble-search
Cycle: 20
Review file to read first: review-stage/20260622-002147-cycle20-quant-pm-copilot-opus.md

Primary objective:
Improve the final quant research paper/report, not just code. Treat Copilot Opus as a read-only senior quant PM reviewer. Use its findings to make the report more credible and submission-ready.

Rules:
- Read AGENTS.md and docs/copilot_opus_reviewer_mcp.md.
- Do not ask the user questions; use best judgment.
- Do not let Copilot edit files. You are the executor.
- Use cloud data only; data/raw, data/processed, and output are linked to the full cloud experiment artifacts.
- Keep Kronos only as a survivorship-bias mitigation/future data-universe route, not empirical alpha evidence.
- Do not resurrect weak MLP/graph/Kronos claims unless evidence supports them.
- Prioritize paper-level fixes: claim discipline, table consistency, ablation interpretation, benchmark framing, transaction-cost/turnover/capacity/survivorship/regime caveats.
- If a reviewer finding requires a focused computation and the data/scripts exist, run it on this cloud server. Use GPU acceleration where the existing scripts support it. Do not start huge unrelated sweeps unless directly needed for the paper.
- If a requested computation is infeasible or data is missing, document that limitation honestly in the report/review-stage notes.
- Run relevant validation: git diff --check, Python compile for touched scripts, LaTeX compile if pdflatex is available.
- Save a scope note under review-stage/ for this cycle.
- Commit coherent changes locally. Push if credentials are available; if push fails, keep the local commit and record that push is pending.

Deliverable for this cycle:
1. Implement the highest-impact safe fixes from the review.
2. Run focused validation/computation as needed.
3. Commit changes if any.
4. Write a concise cycle summary under /root/research_project_aris/output/aris_paper_pm_20260621-193610/cycle_20_codex_summary.md.
