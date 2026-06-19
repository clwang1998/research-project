# Data Directory

Large datasets and generated feature files are intentionally not tracked by Git.

Expected local layout:

- `raw/`: source datasets such as Kaggle S&P 500 files
- `interim/`: typed or intermediate conversion outputs
- `processed/`: generated features, graph files, embeddings, and manifests

Regenerate these files with the scripts in `../scripts/`, or sync them separately with cloud storage/Git LFS if they must be shared across machines.
