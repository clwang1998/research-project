#!/usr/bin/env python3
"""Merge sharded Kronos zero-shot predictions and compute final IC metrics."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from run_kronos_zero_shot import (
    HORIZONS,
    KEY_COLS,
    build_comparison,
    evaluate_predictions,
    load_targets,
    write_summary,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", default="data/processed/features_by_group/targets.parquet")
    parser.add_argument("--out-dir", default="output/kronos_zero_shot")
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--shard-glob", default=None)
    parser.add_argument("--shard-run-names", nargs="+", default=None)
    parser.add_argument("--tokenizer-id", default="NeoQuasar/Kronos-Tokenizer-base")
    parser.add_argument("--model-id", default="NeoQuasar/Kronos-small")
    parser.add_argument("--lookback", type=int, default=512)
    parser.add_argument("--horizons", type=int, nargs="+", default=HORIZONS)
    parser.add_argument("--train-end", default="2018-12-31")
    parser.add_argument("--val-end", default="2020-12-31")
    parser.add_argument("--start-date", default="2005-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--splits", nargs="+", choices=["val", "test"], default=["val", "test"])
    parser.add_argument("--date-stride", type=int, default=1)
    parser.add_argument("--max-dates", type=int, default=None)
    parser.add_argument("--max-symbols", type=int, default=None)
    parser.add_argument("--symbol-sample", choices=["sorted", "random"], default="sorted")
    parser.add_argument("--min-names-per-date", type=int, default=100)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument(
        "--reference-metrics",
        default="output/model_pipeline/target_grid_core_refine_best_metrics.csv",
    )
    args = parser.parse_args()
    args.horizons = sorted(set(args.horizons))
    args.dry_run = False
    args.num_shards = 1
    args.shard_index = 0
    return args


def prediction_paths(args: argparse.Namespace) -> list[Path]:
    out_root = Path(args.out_dir)
    if args.shard_run_names:
        paths = [out_root / run_name / "predictions.parquet" for run_name in args.shard_run_names]
    else:
        pattern = args.shard_glob or f"{args.run_name}_shard*_of*/predictions.parquet"
        paths = sorted(out_root.glob(pattern))

    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing shard prediction files: {missing}")
    if not paths:
        raise FileNotFoundError("No shard prediction files matched")
    return paths


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir) / args.run_name
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = prediction_paths(args)
    predictions = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    predictions = predictions.drop_duplicates(KEY_COLS, keep="last").sort_values(KEY_COLS)
    predictions.to_parquet(out_dir / "predictions.parquet", index=False)

    targets = load_targets(args, args.horizons)
    metrics, _ = evaluate_predictions(args, predictions, targets, out_dir)
    comparison = build_comparison(args, metrics, out_dir)

    metadata = {
        "run_name": args.run_name,
        "model_id": args.model_id,
        "tokenizer_id": args.tokenizer_id,
        "targets": args.targets,
        "lookback": args.lookback,
        "horizons": args.horizons,
        "train_end": args.train_end,
        "val_end": args.val_end,
        "splits": args.splits,
        "date_stride": args.date_stride,
        "max_dates": args.max_dates,
        "max_symbols": args.max_symbols,
        "symbol_sample": args.symbol_sample,
        "target_rows": int(len(targets)),
        "target_dates": int(targets["date"].nunique()),
        "candidate_rows": int(len(predictions)),
        "candidate_dates": int(predictions["date"].nunique()) if not predictions.empty else 0,
        "prediction_rows": int(len(predictions)),
        "source_prediction_files": [str(path) for path in paths],
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    write_summary(args, out_dir, metadata, metrics, comparison)
    print(f"Merged {len(paths)} shard files into {out_dir}")


if __name__ == "__main__":
    main()
