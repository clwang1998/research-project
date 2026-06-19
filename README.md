# Research Project

This repository tracks the reproducible project code, documentation, and lightweight configuration for the S&P 500 research workflow.

## Git Sync Policy

Tracked in Git:

- `scripts/` experiment and data-processing code
- `docs/` research notes and reports
- `requirements.txt`
- `MLP_research_project.pdf`
- lightweight vendored source under `external/`

Kept local and excluded from Git:

- raw, interim, and processed datasets under `data/`
- generated experiment outputs under `output/`
- cloud/archive bundles under `dist/`
- temporary files under `tmp/`
- virtual environments, caches, cookies, and local credentials

This keeps the cloud repository small and avoids publishing credentials or large generated artifacts. Use Git for code/document sync, and use object storage, Git LFS, or the existing cloud bundle scripts for large datasets/results when needed.

## Basic Workflow

```bash
git status
git add .
git commit -m "Update research project"
git push
```

On another machine:

```bash
git pull
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
