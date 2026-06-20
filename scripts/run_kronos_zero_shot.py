#!/usr/bin/env python3
"""Run a Kronos zero-shot prediction benchmark against report targets.

This script intentionally evaluates prediction quality only. It does not create
trading signals, decile portfolios, or backtests. The score used for IC is the
Kronos-predicted simple forward return:

    predicted_close[t + horizon] / close[t] - 1

That score is evaluated against the same 12 target columns used in
`docs/experiment_results_report.md`.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


KEY_COLS = ["date", "symbol"]
HORIZONS = [1, 5, 20]
TARGET_FAMILIES = ["ret", "excess_market", "rank", "excess_sector"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stocks-csv", default="data/raw/sp500_stocks.csv")
    parser.add_argument("--targets", default="data/processed/features_by_group/targets.parquet")
    parser.add_argument("--out-dir", default="output/kronos_zero_shot")
    parser.add_argument("--run-name", default="kronos_small_zero_shot")
    parser.add_argument("--kronos-root", default=None)
    parser.add_argument("--tokenizer-id", default="NeoQuasar/Kronos-Tokenizer-base")
    parser.add_argument("--model-id", default="NeoQuasar/Kronos-small")
    parser.add_argument("--device", default=None)
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
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--min-names-per-date", type=int, default=100)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--top-k", type=int, default=1)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--sample-count", type=int, default=1)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument(
        "--num-shards",
        type=int,
        default=1,
        help="Split evaluation dates into this many disjoint shards.",
    )
    parser.add_argument(
        "--shard-index",
        type=int,
        default=0,
        help="0-based date shard index to run when --num-shards > 1.",
    )
    parser.add_argument(
        "--reference-metrics",
        default="output/model_pipeline/target_grid_core_refine_best_metrics.csv",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the evaluation grid and write metadata, but do not load Kronos or predict.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Append missing predictions when predictions.parquet already exists.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.num_shards < 1:
        raise ValueError("--num-shards must be >= 1")
    if args.shard_index < 0 or args.shard_index >= args.num_shards:
        raise ValueError("--shard-index must satisfy 0 <= shard-index < num-shards")


def target_col(family: str, horizon: int) -> str:
    return f"target_{family}_fwd_{horizon}d"


def score_col(horizon: int) -> str:
    return f"kronos_pred_ret_fwd_{horizon}d"


def split_for_dates(dates: pd.Series, train_end: str, val_end: str) -> pd.Series:
    train_end_ts = pd.Timestamp(train_end)
    val_end_ts = pd.Timestamp(val_end)
    return pd.Series(
        np.select(
            [dates <= train_end_ts, dates <= val_end_ts],
            ["train", "val"],
            default="test",
        ),
        index=dates.index,
    )


def infer_kronos_root(arg_value: str | None) -> Path:
    if arg_value:
        return Path(arg_value)
    candidates = [
        Path("external/Kronos"),
        Path("external/Kronos_src"),
        Path("/tmp/codex-kronos"),
    ]
    for candidate in candidates:
        if (candidate / "model" / "kronos.py").exists():
            return candidate
    raise FileNotFoundError(
        "Could not find a Kronos checkout. Pass --kronos-root /path/to/Kronos "
        "or clone https://github.com/shiyu-coder/Kronos into external/Kronos."
    )


def load_stocks(path: str | Path, start_date: str | None, end_date: str | None) -> dict[str, pd.DataFrame]:
    stocks = pd.read_csv(
        path,
        usecols=["date", "open", "high", "low", "close", "volume", "symbol"],
        dtype={
            "open": "float32",
            "high": "float32",
            "low": "float32",
            "close": "float32",
            "volume": "float32",
            "symbol": "string",
        },
        parse_dates=["date"],
    )
    stocks["symbol"] = stocks["symbol"].str.strip().str.upper()
    stocks = stocks.dropna(subset=["date", "symbol", "open", "high", "low", "close", "volume"])
    if start_date:
        # Keep enough pre-start history for lookback externally by not filtering here.
        pass
    if end_date:
        stocks = stocks.loc[stocks["date"] <= pd.Timestamp(end_date)]

    typical_price = stocks[["open", "high", "low", "close"]].mean(axis=1)
    stocks["amount"] = stocks["volume"] * typical_price
    stocks = stocks.sort_values(["symbol", "date"], kind="mergesort")
    stocks = stocks.drop_duplicates(["symbol", "date"], keep="last")
    cols = ["date", "open", "high", "low", "close", "volume", "amount"]
    return {str(sym): g.loc[:, cols].reset_index(drop=True) for sym, g in stocks.groupby("symbol", sort=True)}


def load_targets(args: argparse.Namespace, horizons: list[int]) -> pd.DataFrame:
    target_cols = [target_col(family, h) for h in horizons for family in TARGET_FAMILIES]
    read_cols = KEY_COLS + ["sector"] + target_cols
    targets = pd.read_parquet(args.targets, columns=read_cols)
    targets["symbol"] = targets["symbol"].astype(str).str.strip().str.upper()
    targets["split"] = split_for_dates(targets["date"], args.train_end, args.val_end)
    targets = targets.loc[targets["split"].isin(args.splits)].copy()
    if args.start_date:
        targets = targets.loc[targets["date"] >= pd.Timestamp(args.start_date)]
    if args.end_date:
        targets = targets.loc[targets["date"] <= pd.Timestamp(args.end_date)]
    targets = targets.dropna(subset=target_cols, how="all")
    if args.max_symbols:
        symbols = sorted(targets["symbol"].unique())
        if args.symbol_sample == "random":
            rng = np.random.default_rng(args.seed)
            symbols = sorted(rng.choice(symbols, size=min(args.max_symbols, len(symbols)), replace=False))
        else:
            symbols = symbols[: args.max_symbols]
        targets = targets.loc[targets["symbol"].isin(symbols)].copy()
    return targets.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)


def selected_dates(targets: pd.DataFrame, stride: int, max_dates: int | None) -> pd.Index:
    dates = pd.Index(sorted(targets["date"].unique()))
    if stride > 1:
        dates = dates[::stride]
    if max_dates is not None:
        dates = dates[:max_dates]
    return dates


def shard_dates(dates: pd.Index, num_shards: int, shard_index: int) -> pd.Index:
    if num_shards == 1:
        return dates
    return pd.Index([dt for idx, dt in enumerate(dates) if idx % num_shards == shard_index])


def find_position(dates: np.ndarray, dt: pd.Timestamp) -> int | None:
    key = np.datetime64(dt.to_datetime64())
    pos = int(np.searchsorted(dates, key))
    if pos >= len(dates) or dates[pos] != key:
        return None
    return pos


def build_candidate_grid(
    stocks_by_symbol: dict[str, pd.DataFrame],
    targets: pd.DataFrame,
    eval_dates: pd.Index,
    lookback: int,
    max_horizon: int,
) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    date_arrays = {
        sym: g["date"].to_numpy(dtype="datetime64[ns]")
        for sym, g in stocks_by_symbol.items()
    }
    rows: list[dict[str, Any]] = []
    target_by_date = targets.loc[targets["date"].isin(eval_dates)].groupby("date", sort=True)
    for dt, date_targets in target_by_date:
        for sym in date_targets["symbol"].astype(str):
            dates = date_arrays.get(sym)
            if dates is None:
                continue
            pos = find_position(dates, pd.Timestamp(dt))
            if pos is None or pos + max_horizon >= len(dates):
                continue
            if pos + 1 < lookback:
                continue
            rows.append({"date": pd.Timestamp(dt), "symbol": sym})
    return pd.DataFrame(rows), date_arrays


def load_kronos(args: argparse.Namespace):
    kronos_root = infer_kronos_root(args.kronos_root)
    sys.path.insert(0, str(kronos_root))
    from model import Kronos, KronosPredictor, KronosTokenizer

    import torch

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    tokenizer = KronosTokenizer.from_pretrained(args.tokenizer_id)
    model = Kronos.from_pretrained(args.model_id)
    tokenizer.eval()
    model.eval()
    predictor = KronosPredictor(model, tokenizer, device=args.device, max_context=args.lookback)
    return predictor, kronos_root


def predict_rows(
    args: argparse.Namespace,
    predictor: Any,
    stocks_by_symbol: dict[str, pd.DataFrame],
    candidate_grid: pd.DataFrame,
    already_done: set[tuple[pd.Timestamp, str]],
    checkpoint_path: Path,
    existing_predictions: pd.DataFrame,
) -> pd.DataFrame:
    max_horizon = max(args.horizons)
    records: list[dict[str, Any]] = []
    start = time.time()

    for date_idx, (dt, group) in enumerate(candidate_grid.groupby("date", sort=True), start=1):
        group = group.sort_values("symbol")
        if already_done:
            group = group.loc[
                ~group["symbol"].map(lambda s: (pd.Timestamp(dt), str(s)) in already_done)
            ]
        if group.empty:
            continue

        prepared: list[tuple[str, pd.DataFrame, pd.Series, pd.Series, float]] = []
        for sym in group["symbol"].astype(str):
            stock = stocks_by_symbol[sym]
            dates = stock["date"].to_numpy(dtype="datetime64[ns]")
            pos = find_position(dates, pd.Timestamp(dt))
            if pos is None:
                continue
            hist = stock.iloc[pos + 1 - args.lookback : pos + 1].copy()
            future = stock.iloc[pos + 1 : pos + 1 + max_horizon].copy()
            if len(hist) != args.lookback or len(future) != max_horizon:
                continue
            x_df = hist[["open", "high", "low", "close", "volume", "amount"]].reset_index(drop=True)
            prepared.append(
                (
                    sym,
                    x_df,
                    hist["date"].reset_index(drop=True),
                    future["date"].reset_index(drop=True),
                    float(hist["close"].iloc[-1]),
                )
            )

        for start_idx in range(0, len(prepared), args.batch_size):
            batch = prepared[start_idx : start_idx + args.batch_size]
            if not batch:
                continue
            pred_dfs = predictor.predict_batch(
                df_list=[item[1] for item in batch],
                x_timestamp_list=[item[2] for item in batch],
                y_timestamp_list=[item[3] for item in batch],
                pred_len=max_horizon,
                T=args.temperature,
                top_k=args.top_k,
                top_p=args.top_p,
                sample_count=args.sample_count,
                verbose=False,
            )
            for (sym, _, _, _, last_close), pred_df in zip(batch, pred_dfs):
                row: dict[str, Any] = {"date": pd.Timestamp(dt), "symbol": sym}
                for h in args.horizons:
                    row[score_col(h)] = float(pred_df["close"].iloc[h - 1] / last_close - 1.0)
                records.append(row)

        elapsed = time.time() - start
        if records:
            checkpoint = pd.concat(
                [existing_predictions, pd.DataFrame(records)],
                ignore_index=True,
            )
            checkpoint = checkpoint.drop_duplicates(KEY_COLS, keep="last").sort_values(KEY_COLS)
            checkpoint.to_parquet(checkpoint_path, index=False)
        print(
            f"[{date_idx}/{candidate_grid['date'].nunique()}] {pd.Timestamp(dt).date()} "
            f"predicted={len(records):,} elapsed={elapsed/60:.1f}m",
            flush=True,
        )

    return pd.DataFrame(records)


def spearman_by_date(df: pd.DataFrame, score: str, target: str, min_names: int) -> pd.DataFrame:
    rows = []
    for dt, g in df.groupby("date", sort=True):
        h = g[[score, target]].dropna()
        if len(h) < min_names:
            continue
        rows.append({"date": dt, "rank_ic": h[score].rank().corr(h[target].rank()), "n": len(h)})
    return pd.DataFrame(rows)


def summarize_ic(ic: pd.DataFrame) -> dict[str, float | int]:
    vals = ic["rank_ic"].dropna() if not ic.empty else pd.Series(dtype="float64")
    if vals.empty:
        return {"mean_rank_ic": math.nan, "rank_ic_std": math.nan, "rank_ic_ir": math.nan, "dates": 0}
    std = float(vals.std(ddof=1))
    return {
        "mean_rank_ic": float(vals.mean()),
        "rank_ic_std": std,
        "rank_ic_ir": float(vals.mean() / (std + 1e-12) * math.sqrt(252.0)),
        "dates": int(len(vals)),
    }


def evaluate_predictions(
    args: argparse.Namespace,
    predictions: pd.DataFrame,
    targets: pd.DataFrame,
    out_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    merged = predictions.merge(targets, on=KEY_COLS, how="inner", sort=False)
    rank_ic_rows: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []

    for h in args.horizons:
        pred_col = score_col(h)
        for family in TARGET_FAMILIES:
            tgt = target_col(family, h)
            for split, split_df in merged.groupby("split", sort=True):
                if split not in args.splits:
                    continue
                ic = spearman_by_date(split_df, pred_col, tgt, args.min_names_per_date)
                if not ic.empty:
                    ic["split"] = split
                    ic["horizon"] = h
                    ic["target_family"] = family
                    ic["target_col"] = tgt
                    ic["score_col"] = pred_col
                    rank_ic_rows.append(ic)
                metric_rows.append(
                    {
                        "run_name": args.run_name,
                        "model": "kronos_zero_shot",
                        "model_id": args.model_id,
                        "target_col": tgt,
                        "horizon": h,
                        "target_family": family,
                        "score": pred_col,
                        "split": split,
                        **summarize_ic(ic),
                        "rows": int(split_df[[pred_col, tgt]].dropna().shape[0]),
                    }
                )

    rank_ic = pd.concat(rank_ic_rows, ignore_index=True) if rank_ic_rows else pd.DataFrame()
    metrics = pd.DataFrame(metric_rows).sort_values(["horizon", "target_family", "split"])
    rank_ic.to_csv(out_dir / "rank_ic_by_date.csv", index=False)
    metrics.to_csv(out_dir / "metrics.csv", index=False)
    return metrics, rank_ic


def build_comparison(args: argparse.Namespace, metrics: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    ref_path = Path(args.reference_metrics)
    if not ref_path.exists() or metrics.empty:
        return pd.DataFrame()

    ref = pd.read_csv(ref_path)
    ref_test = ref.loc[(ref["score"] == "model_score") & (ref["split"] == "test")].copy()
    ref_best_idx = ref_test.groupby("target_col")["rank_ic_ir"].idxmax()
    ref_best = ref_test.loc[
        ref_best_idx,
        ["target_col", "model", "grid_tag", "mean_rank_ic", "rank_ic_ir"],
    ].rename(
        columns={
            "model": "report_best_model",
            "grid_tag": "report_best_grid",
            "mean_rank_ic": "report_best_test_ic",
            "rank_ic_ir": "report_best_test_icir",
        }
    )

    ref_baseline = (
        ref.loc[(ref["score"] == "baseline_score") & (ref["split"] == "test")]
        .drop_duplicates("target_col")
        [["target_col", "mean_rank_ic", "rank_ic_ir"]]
        .rename(
            columns={
                "mean_rank_ic": "report_baseline_test_ic",
                "rank_ic_ir": "report_baseline_test_icir",
            }
        )
    )

    kronos_test = metrics.loc[metrics["split"] == "test"].copy()
    kronos_test = kronos_test[
        ["target_col", "horizon", "target_family", "mean_rank_ic", "rank_ic_ir", "dates", "rows"]
    ].rename(
        columns={
            "mean_rank_ic": "kronos_test_ic",
            "rank_ic_ir": "kronos_test_icir",
            "dates": "kronos_test_dates",
            "rows": "kronos_test_rows",
        }
    )
    out = kronos_test.merge(ref_best, on="target_col", how="left").merge(
        ref_baseline, on="target_col", how="left"
    )
    out["kronos_minus_report_best_icir"] = out["kronos_test_icir"] - out["report_best_test_icir"]
    out["kronos_minus_baseline_icir"] = out["kronos_test_icir"] - out["report_baseline_test_icir"]
    out = out.sort_values(["horizon", "target_family"])
    out.to_csv(out_dir / "comparison_to_report.csv", index=False)
    return out


def write_summary(
    args: argparse.Namespace,
    out_dir: Path,
    metadata: dict[str, Any],
    metrics: pd.DataFrame | None,
    comparison: pd.DataFrame | None,
) -> None:
    lines = [
        "# Kronos Zero-Shot IC Benchmark",
        "",
        f"- Model: `{args.model_id}`",
        f"- Tokenizer: `{args.tokenizer_id}`",
        f"- Lookback: {args.lookback}",
        f"- Horizons: {', '.join(map(str, args.horizons))}",
        f"- Splits: {', '.join(args.splits)}",
        f"- Date stride: {args.date_stride}",
        f"- Max dates: {args.max_dates}",
        f"- Max symbols: {args.max_symbols}",
        f"- Symbol sample: {args.symbol_sample}",
        f"- Shard: {args.shard_index}/{args.num_shards}",
        f"- Dry run: {args.dry_run}",
        "",
        "## Coverage",
        "",
        f"- Evaluation candidate rows: {metadata.get('candidate_rows', 0):,}",
        f"- Evaluation dates: {metadata.get('candidate_dates', 0):,}",
        f"- Target rows after filters: {metadata.get('target_rows', 0):,}",
        "",
    ]
    if metrics is not None and not metrics.empty:
        lines.extend(["## Metrics", ""])
        show = metrics.loc[:, ["horizon", "target_family", "split", "mean_rank_ic", "rank_ic_ir", "dates", "rows"]]
        lines.append(show.to_markdown(index=False, floatfmt=".4f"))
        lines.append("")
    if comparison is not None and not comparison.empty:
        lines.extend(["## Test Comparison To Report", ""])
        cols = [
            "horizon",
            "target_family",
            "kronos_test_ic",
            "kronos_test_icir",
            "report_best_model",
            "report_best_test_icir",
            "report_baseline_test_icir",
            "kronos_minus_report_best_icir",
        ]
        lines.append(comparison.loc[:, cols].to_markdown(index=False, floatfmt=".4f"))
        lines.append("")
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    validate_args(args)
    args.horizons = sorted(set(args.horizons))
    max_horizon = max(args.horizons)
    out_dir = Path(args.out_dir) / args.run_name
    out_dir.mkdir(parents=True, exist_ok=True)

    targets = load_targets(args, args.horizons)
    eval_dates = selected_dates(targets, args.date_stride, args.max_dates)
    all_eval_dates = eval_dates
    eval_dates = shard_dates(eval_dates, args.num_shards, args.shard_index)
    stocks_by_symbol = load_stocks(args.stocks_csv, args.start_date, args.end_date)
    candidate_grid, _ = build_candidate_grid(
        stocks_by_symbol, targets, eval_dates, args.lookback, max_horizon
    )

    metadata: dict[str, Any] = {
        "run_name": args.run_name,
        "model_id": args.model_id,
        "tokenizer_id": args.tokenizer_id,
        "stocks_csv": args.stocks_csv,
        "targets": args.targets,
        "lookback": args.lookback,
        "horizons": args.horizons,
        "train_end": args.train_end,
        "val_end": args.val_end,
        "splits": args.splits,
        "date_stride": args.date_stride,
        "max_dates": args.max_dates,
        "num_shards": args.num_shards,
        "shard_index": args.shard_index,
        "all_eval_dates": int(len(all_eval_dates)),
        "shard_eval_dates": int(len(eval_dates)),
        "max_symbols": args.max_symbols,
        "symbol_sample": args.symbol_sample,
        "target_rows": int(len(targets)),
        "target_dates": int(targets["date"].nunique()),
        "candidate_rows": int(len(candidate_grid)),
        "candidate_dates": int(candidate_grid["date"].nunique()) if not candidate_grid.empty else 0,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    candidate_grid.to_csv(out_dir / "candidate_grid.csv", index=False)

    if args.dry_run:
        write_summary(args, out_dir, metadata, None, None)
        print(json.dumps(metadata, indent=2))
        return

    existing = pd.DataFrame()
    already_done: set[tuple[pd.Timestamp, str]] = set()
    pred_path = out_dir / "predictions.parquet"
    if args.resume and pred_path.exists():
        existing = pd.read_parquet(pred_path)
        already_done = {
            (pd.Timestamp(row.date), str(row.symbol))
            for row in existing[["date", "symbol"]].itertuples(index=False)
        }

    predictor, kronos_root = load_kronos(args)
    metadata["kronos_root"] = str(kronos_root)
    new_predictions = predict_rows(
        args,
        predictor,
        stocks_by_symbol,
        candidate_grid,
        already_done,
        pred_path,
        existing,
    )
    predictions = pd.concat([existing, new_predictions], ignore_index=True)
    predictions = predictions.drop_duplicates(KEY_COLS, keep="last").sort_values(KEY_COLS)
    predictions.to_parquet(pred_path, index=False)

    metrics, _ = evaluate_predictions(args, predictions, targets, out_dir)
    comparison = build_comparison(args, metrics, out_dir)
    metadata["prediction_rows"] = int(len(predictions))
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    write_summary(args, out_dir, metadata, metrics, comparison)
    print(f"Wrote Kronos zero-shot outputs to {out_dir}")


if __name__ == "__main__":
    main()
