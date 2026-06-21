#!/usr/bin/env python3
"""Build Kaggle/Ubiquant-style date-level aggregate features.

The Ubiquant 8th-place writeup used per-time-id feature aggregates as market
state context. For this S&P 500 panel, the analogous leakage-safe feature is a
same-date cross-sectional aggregate computed only from features available at
date t. The aggregate is constant across stocks on a date, so it primarily helps
tree models learn regime-conditional interactions with stock-level features.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq


KEY_COLS = ["date", "symbol"]

DEFAULT_FEATURES_BY_FILE = {
    "price_momentum.parquet": [
        "ret_1d",
        "ret_5d",
        "ret_20d",
        "ret_60d",
        "ret_120d",
        "mom_20d_skip_5d",
        "mom_60d_skip_20d",
        "mom_120d_skip_20d",
        "mom_252d_skip_21d",
        "mom_accel_5_20",
        "mom_accel_20_60",
    ],
    "volatility.parquet": [
        "vol_20d",
        "vol_60d",
        "downside_vol_20d",
        "vol_ratio_20_60",
        "idio_vol_60d",
        "beta_60d",
    ],
    "trend_technical.parquet": [
        "rsi_14d",
        "sma_gap_20d",
        "sma_gap_50d",
        "boll_z_20d",
        "channel_pos_20d",
    ],
    "liquidity_volume.parquet": [
        "log_dollar_volume",
        "volume_z_20d",
        "dollar_volume_z_20d",
        "volume_mom_20d",
        "amihud_20d",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-dir", default="data/processed/features_by_group")
    parser.add_argument("--out-file", default="data/processed/features_by_group/kaggle_time_agg.parquet")
    parser.add_argument("--base-feature-map", default="data/processed/feature_columns_by_group.csv")
    parser.add_argument(
        "--feature-map-out",
        default="data/processed/feature_columns_by_group_kaggle_time_agg.csv",
    )
    parser.add_argument("--rolling-windows", nargs="+", type=int, default=[20, 60])
    parser.add_argument("--compression", default="zstd")
    return parser.parse_args()


def available_columns(path: Path) -> set[str]:
    return set(pq.ParquetFile(path).schema_arrow.names)


def aggregate_file(path: Path, columns: list[str], rolling_windows: list[int]) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=["date", *columns])
    frame["date"] = pd.to_datetime(frame["date"])
    grouped = frame.groupby("date", sort=True)[columns]
    means = grouped.mean().add_prefix("ktagg_mean_")
    stds = grouped.std().add_prefix("ktagg_std_")
    out = pd.concat([means, stds], axis=1).sort_index()
    for col in columns:
        mean_col = f"ktagg_mean_{col}"
        std_col = f"ktagg_std_{col}"
        for window in rolling_windows:
            out[f"ktagg_mean_{col}_roll{window}d"] = (
                out[mean_col].rolling(window, min_periods=max(3, window // 2)).mean()
            )
            out[f"ktagg_std_{col}_roll{window}d"] = (
                out[std_col].rolling(window, min_periods=max(3, window // 2)).mean()
            )
    return out.reset_index()


def main() -> None:
    args = parse_args()
    feature_dir = Path(args.feature_dir)
    out_file = Path(args.out_file)

    target_path = feature_dir / "targets.parquet"
    keys = pd.read_parquet(target_path, columns=KEY_COLS)
    keys["date"] = pd.to_datetime(keys["date"])
    dates = pd.DataFrame({"date": sorted(keys["date"].dropna().unique())})

    date_frames = [dates]
    used: dict[str, list[str]] = {}
    for file_name, requested in DEFAULT_FEATURES_BY_FILE.items():
        path = feature_dir / file_name
        if not path.exists():
            continue
        present = available_columns(path)
        cols = [c for c in requested if c in present]
        if not cols:
            continue
        used[file_name] = cols
        date_frames.append(aggregate_file(path, cols, args.rolling_windows))

    date_features = date_frames[0]
    for frame in date_frames[1:]:
        date_features = date_features.merge(frame, on="date", how="left", sort=False)
    feature_cols = [c for c in date_features.columns if c != "date"]
    for col in feature_cols:
        date_features[col] = pd.to_numeric(date_features[col], errors="coerce").astype("float32")

    out = keys.merge(date_features, on="date", how="left", sort=False)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(out_file, index=False, compression=args.compression)

    base_map = pd.read_csv(args.base_feature_map)
    extra_map = pd.DataFrame({"file": out_file.name, "column": feature_cols})
    merged_map = (
        pd.concat([base_map, extra_map], ignore_index=True)
        .drop_duplicates(["file", "column"])
        .sort_values(["file", "column"], kind="mergesort")
    )
    feature_map_out = Path(args.feature_map_out)
    feature_map_out.parent.mkdir(parents=True, exist_ok=True)
    merged_map.to_csv(feature_map_out, index=False)

    summary = {
        "out_file": str(out_file),
        "feature_map_out": str(feature_map_out),
        "rows": int(len(out)),
        "date_features": int(len(feature_cols)),
        "source_columns": used,
        "rolling_windows": args.rolling_windows,
        "note": "Date-level aggregates use only same-date tabular features and trailing rolling windows.",
    }
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
