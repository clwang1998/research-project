#!/usr/bin/env python3
"""Build S&P 500 features as grouped Parquet files.

This is the production path for the full dataset. It avoids keeping the full
500+ column panel in memory by writing each feature group, then dropping columns
that are not needed by later groups.
"""

from __future__ import annotations

import argparse
import gc
import json
import time
from pathlib import Path

import pandas as pd

from make_features import (
    FeatureManifest,
    add_beta_and_correlation_features,
    add_calendar_and_metadata_features,
    add_cross_sectional_features,
    add_liquidity_features,
    add_market_industry_features,
    add_peer_and_style_features,
    add_price_return_features,
    add_targets,
    add_trend_features,
    add_volatility_features,
    load_inputs,
    optimize_dtypes,
    prepare_metadata,
)


RAW_COLS = {
    "date",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "company",
    "sector",
    "sub_industry",
    "date_added",
    "founded_year",
    "legacy_founded_year",
    "hq_city",
    "hq_state",
    "hq_region",
}

CROSS_SECTIONAL_INPUTS = {
    "ret_1d",
    "ret_5d",
    "ret_20d",
    "ret_60d",
    "ret_120d",
    "mom_252d_skip_21d",
    "vol_20d",
    "vol_60d",
    "downside_vol_20d",
    "parkinson_vol_20d",
    "gk_vol_20d",
    "volume_z_20d",
    "dollar_volume_z_20d",
    "log_dollar_volume",
    "amihud_20d",
    "rsi_14d",
    "sma_gap_20d",
    "sma_gap_50d",
    "sma_gap_200d",
    "boll_z_20d",
    "channel_pos_20d",
    "channel_pos_60d",
    "beta_60d",
    "idio_vol_60d",
    "excess_sector_ret_20d",
    "excess_subind_ret_20d",
    "firm_age_years",
    "sp500_membership_age_years",
}

PEER_INPUTS = {
    "ret_1d",
    "ret_5d",
    "ret_20d",
    "ret_60d",
    "vol_20d",
    "vol_60d",
    "rsi_14d",
    "volume_z_20d",
    "sma_gap_20d",
    "beta_60d",
    "log_dollar_volume",
}

INDUSTRY_INPUTS = {
    "ret_1d",
    "ret_5d",
    "ret_20d",
    "ret_60d",
    "dollar_volume",
    "log_dollar_volume",
}

STAT_INPUTS = {"market_ret_1d"}

PRECOMPUTED_METADATA_FEATURES = {
    "sector_code",
    "sub_industry_code",
    "hq_city_code",
    "hq_state_code",
    "hq_region_code",
    "sector_n_companies",
    "sub_industry_n_companies",
    "hq_city_n_companies",
    "hq_state_n_companies",
    "hq_region_n_companies",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stocks", default="data/interim/sp500_stocks_typed.parquet")
    parser.add_argument("--companies", default="data/interim/sp500_companies_typed.parquet")
    parser.add_argument("--out-dir", default="data/processed/features_by_group")
    parser.add_argument("--manifest", default="data/processed/feature_manifest.csv")
    parser.add_argument("--metadata", default="data/processed/feature_group_metadata.json")
    parser.add_argument("--max-symbols", type=int, default=None)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--min-history-days", type=int, default=0)
    parser.add_argument("--compression", default="zstd")
    return parser.parse_args()


def now() -> float:
    return time.perf_counter()


def log_stage(stage: str, start: float, df: pd.DataFrame) -> dict[str, object]:
    elapsed = time.perf_counter() - start
    memory_mb = df.memory_usage(deep=True).sum() / 1024**2
    record = {
        "stage": stage,
        "seconds": round(elapsed, 3),
        "columns_in_working_frame": int(df.shape[1]),
        "working_frame_memory_mb": round(memory_mb, 1),
    }
    print(json.dumps(record), flush=True)
    return record


def output_keys(df: pd.DataFrame) -> list[str]:
    keys = ["date", "symbol"]
    for col in ["sector", "sub_industry", "hq_state", "hq_region"]:
        if col in df.columns:
            keys.append(col)
    return keys


def write_group(
    df: pd.DataFrame,
    out_dir: Path,
    group_name: str,
    columns: list[str],
    compression: str,
) -> str:
    columns = [c for c in columns if c in df.columns]
    keys = output_keys(df)
    out = optimize_dtypes(df.loc[:, keys + columns].copy())
    path = out_dir / f"{group_name}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False, compression=compression)
    return str(path)


def drop_unneeded(df: pd.DataFrame, keep_cols: set[str]) -> pd.DataFrame:
    keep_existing = [c for c in df.columns if c in keep_cols or c in RAW_COLS]
    compact = df.loc[:, keep_existing].copy()
    gc.collect()
    return compact


def add_and_write(
    df: pd.DataFrame,
    manifest: FeatureManifest,
    out_dir: Path,
    group_name: str,
    compression: str,
    func,
    keep_cols: set[str],
    extra_output_cols: set[str] | None = None,
    *args,
) -> tuple[pd.DataFrame, dict[str, object], list[str]]:
    before = set(df.columns)
    start = now()
    func(df, *args, manifest) if args else func(df, manifest)
    new_cols = [c for c in df.columns if c not in before]
    if extra_output_cols:
        for col in sorted(extra_output_cols):
            if col in df.columns and col not in new_cols:
                new_cols.append(col)
    path = write_group(df, out_dir, group_name, new_cols, compression)
    keep_cols.update(c for c in new_cols if c in CROSS_SECTIONAL_INPUTS)
    keep_cols.update(c for c in new_cols if c in PEER_INPUTS)
    keep_cols.update(c for c in new_cols if c in INDUSTRY_INPUTS)
    keep_cols.update(c for c in new_cols if c in STAT_INPUTS)
    keep_cols.update(c for c in new_cols if c.startswith("sector_ret_"))
    keep_cols.update(c for c in new_cols if c.startswith("subind_ret_"))
    keep_cols.update(c for c in new_cols if c.startswith("excess_"))
    keep_cols.update(c for c in new_cols if c in {"sector_code", "sub_industry_code"})
    record = log_stage(group_name, start, df)
    record["file"] = path
    record["new_columns"] = len(new_cols)
    df = drop_unneeded(df, keep_cols)
    return df, record, new_cols


def build(args: argparse.Namespace) -> dict[str, object]:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = FeatureManifest(rows=[])

    total_start = now()
    stocks, companies, price_col = load_inputs(
        args.stocks,
        args.companies,
        max_symbols=args.max_symbols,
        start_date=args.start_date,
        end_date=args.end_date,
        min_history_days=args.min_history_days,
    )
    metadata = prepare_metadata(companies)
    df = stocks.merge(metadata, on="symbol", how="left", sort=False)
    df = df.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)
    if price_col != "close":
        df["close"] = df[price_col]

    keep_cols = set(RAW_COLS)
    records: list[dict[str, object]] = []
    files: dict[str, str] = {}
    group_columns: dict[str, list[str]] = {}

    def run_group(
        name: str,
        func,
        *func_args,
        extra_output_cols: set[str] | None = None,
    ) -> None:
        nonlocal df
        df, record, cols = add_and_write(
            df,
            manifest,
            out_dir,
            name,
            args.compression,
            func,
            keep_cols,
            extra_output_cols,
            *func_args,
        )
        records.append(record)
        files[name] = str(record["file"])
        group_columns[name] = cols

    run_group(
        "calendar_metadata",
        add_calendar_and_metadata_features,
        extra_output_cols=PRECOMPUTED_METADATA_FEATURES,
    )
    keep_cols.update({"firm_age_years", "sp500_membership_age_years"})

    run_group("price_momentum", add_price_return_features, price_col)
    run_group("volatility", add_volatility_features)
    run_group("trend_technical", add_trend_features, price_col)
    run_group("liquidity_volume", add_liquidity_features)

    df = df.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)
    run_group("market_industry", add_market_industry_features)

    df = df.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)
    run_group("statistical_linkage", add_beta_and_correlation_features)

    df = df.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)
    run_group("peer_style_geography", add_peer_and_style_features)
    run_group("cross_sectional", add_cross_sectional_features)

    df = df.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)
    run_group("targets", add_targets, price_col)

    manifest_df = manifest.to_frame()
    Path(args.manifest).parent.mkdir(parents=True, exist_ok=True)
    manifest_df.to_csv(args.manifest, index=False)

    metadata_out = {
        "rows": int(len(df)),
        "symbols": int(df["symbol"].nunique()),
        "date_min": str(df["date"].min().date()),
        "date_max": str(df["date"].max().date()),
        "price_column_used": price_col,
        "out_dir": str(out_dir),
        "files": files,
        "group_columns": {k: len(v) for k, v in group_columns.items()},
        "feature_manifest": str(args.manifest),
        "manifest_rows": int(len(manifest_df)),
        "feature_columns": int((manifest_df["category"] != "target").sum()),
        "target_columns": int((manifest_df["category"] == "target").sum()),
        "stages": records,
        "total_seconds": round(time.perf_counter() - total_start, 3),
        "join_keys": ["date", "symbol"],
        "note": "Feature groups are stored separately to avoid a single very wide in-memory panel. Join on date and symbol when a combined matrix is needed.",
    }
    Path(args.metadata).parent.mkdir(parents=True, exist_ok=True)
    Path(args.metadata).write_text(json.dumps(metadata_out, indent=2), encoding="utf-8")
    print(json.dumps(metadata_out, indent=2), flush=True)
    return metadata_out


def main() -> None:
    args = parse_args()
    build(args)


if __name__ == "__main__":
    main()
