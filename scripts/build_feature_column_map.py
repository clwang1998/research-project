#!/usr/bin/env python3
"""Build the feature-column map consumed by run_model_pipeline.py.

The grouped feature builder writes one Parquet file per feature family. The
model runner needs a compact CSV mapping each usable feature column back to the
file that stores it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


KEY_COLS = {"date", "symbol"}
META_COLS = {"sector", "sub_industry", "hq_state", "hq_region"}
TARGET_PREFIX = "target_"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-dir", default="data/processed/features_by_group")
    parser.add_argument("--out", default="data/processed/feature_columns_by_group.csv")
    parser.add_argument(
        "--include-meta",
        action="store_true",
        help="Include metadata/context columns such as sector and hq_region.",
    )
    parser.add_argument(
        "--include-targets",
        action="store_true",
        help="Include target_* columns from targets.parquet.",
    )
    return parser.parse_args()


def parquet_columns(path: Path) -> list[str]:
    return pq.ParquetFile(path).schema_arrow.names


def main() -> None:
    args = parse_args()
    feature_dir = Path(args.feature_dir)
    if not feature_dir.exists():
        raise FileNotFoundError(f"feature dir not found: {feature_dir}")

    rows: list[dict[str, str]] = []
    skipped_files: list[str] = []
    for path in sorted(feature_dir.glob("*.parquet")):
        columns = parquet_columns(path)
        file_rows = 0
        for col in columns:
            if col in KEY_COLS:
                continue
            if not args.include_meta and col in META_COLS:
                continue
            if not args.include_targets and col.startswith(TARGET_PREFIX):
                continue
            rows.append({"file": path.name, "column": col})
            file_rows += 1
        if file_rows == 0:
            skipped_files.append(path.name)

    if not rows:
        raise ValueError(f"no feature columns found under {feature_dir}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows).drop_duplicates(["file", "column"])
    frame = frame.sort_values(["file", "column"], kind="mergesort")
    frame.to_csv(out, index=False)

    summary = {
        "feature_dir": str(feature_dir),
        "out": str(out),
        "files_scanned": len(list(feature_dir.glob("*.parquet"))),
        "feature_columns": int(len(frame)),
        "skipped_files": skipped_files,
        "include_meta": bool(args.include_meta),
        "include_targets": bool(args.include_targets),
    }
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
