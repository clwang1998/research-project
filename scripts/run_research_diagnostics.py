#!/usr/bin/env python3
"""Generate EDA diagnostics for the stock-return modeling report."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stocks", default="data/interim/sp500_stocks_typed.parquet")
    parser.add_argument("--targets", default="data/processed/features_by_group/targets.parquet")
    parser.add_argument("--out-dir", default="output/diagnostics")
    parser.add_argument("--start-date", default="2005-01-01")
    parser.add_argument("--min-names-per-date", type=int, default=100)
    return parser.parse_args()


def spearman_by_date(df: pd.DataFrame, score: str, target: str, min_names: int) -> pd.DataFrame:
    rows = []
    for dt, g in df.groupby("date", sort=True):
        h = g[[score, target]].dropna()
        if len(h) < min_names:
            continue
        rows.append({"date": dt, "rank_ic": h[score].rank().corr(h[target].rank()), "n": len(h)})
    return pd.DataFrame(rows)


def safe_stat(series: pd.Series, fn: str) -> float | None:
    vals = series.dropna()
    if vals.empty:
        return None
    if fn == "mean":
        return float(vals.mean())
    if fn == "std":
        return float(vals.std(ddof=1))
    if fn == "median":
        return float(vals.median())
    if fn == "min":
        return float(vals.min())
    if fn == "max":
        return float(vals.max())
    raise ValueError(fn)


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stocks = pd.read_parquet(args.stocks)
    targets = pd.read_parquet(args.targets)
    stocks = stocks.loc[stocks["date"] >= pd.Timestamp(args.start_date)].copy()
    targets = targets.loc[targets["date"] >= pd.Timestamp(args.start_date)].copy()
    stocks = stocks.sort_values(["symbol", "date"], kind="mergesort")

    price_cols = ["open", "high", "low", "close", "volume"]
    data_quality = {
        "rows": int(len(stocks)),
        "symbols": int(stocks["symbol"].nunique()),
        "date_min": str(stocks["date"].min().date()),
        "date_max": str(stocks["date"].max().date()),
        "duplicate_symbol_dates": int(stocks.duplicated(["date", "symbol"]).sum()),
        "missing_by_column": {c: int(stocks[c].isna().sum()) for c in ["date", "symbol", *price_cols]},
        "non_positive_close_rows": int((stocks["close"] <= 0).sum()),
        "non_positive_volume_rows": int((stocks["volume"] <= 0).sum()),
        "ohlc_inversion_rows": int(
            ((stocks["high"] < stocks[["open", "close", "low"]].max(axis=1))
             | (stocks["low"] > stocks[["open", "close", "high"]].min(axis=1))).sum()
        ),
    }

    stocks["simple_ret_1d"] = stocks.groupby("symbol", sort=False)["close"].pct_change()
    stocks["log_ret_1d"] = np.log(stocks["close"]).groupby(stocks["symbol"], sort=False).diff()
    stocks["abs_log_ret_1d"] = stocks["log_ret_1d"].abs()
    stocks["close_lag1"] = stocks.groupby("symbol", sort=False)["close"].shift(1)
    stocks["raw_price_level"] = stocks["close"]

    return_diag = {
        "simple_return": {
            "mean": safe_stat(stocks["simple_ret_1d"], "mean"),
            "std": safe_stat(stocks["simple_ret_1d"], "std"),
            "min": safe_stat(stocks["simple_ret_1d"], "min"),
            "max": safe_stat(stocks["simple_ret_1d"], "max"),
        },
        "log_return": {
            "mean": safe_stat(stocks["log_ret_1d"], "mean"),
            "std": safe_stat(stocks["log_ret_1d"], "std"),
            "min": safe_stat(stocks["log_ret_1d"], "min"),
            "max": safe_stat(stocks["log_ret_1d"], "max"),
        },
        "simple_minus_log_abs_mean": float(
            (stocks["simple_ret_1d"] - stocks["log_ret_1d"]).abs().dropna().mean()
        ),
        "log_additivity_example": {},
    }

    sample = stocks.loc[stocks["symbol"] == stocks["symbol"].iloc[0]].copy()
    sample["log_ret_5d_sum"] = sample["log_ret_1d"].rolling(5).sum()
    sample["log_ret_5d_direct"] = np.log(sample["close"] / sample["close"].shift(5))
    diff = (sample["log_ret_5d_sum"] - sample["log_ret_5d_direct"]).abs().dropna()
    return_diag["log_additivity_example"] = {
        "symbol": str(stocks["symbol"].iloc[0]),
        "max_abs_diff_sum_vs_direct_5d": float(diff.max()) if not diff.empty else None,
    }

    autocorr_rows = []
    for sym, g in stocks.groupby("symbol", sort=False):
        r = g["log_ret_1d"].dropna()
        if len(r) < 252:
            continue
        autocorr_rows.append(
            {
                "symbol": sym,
                "ret_autocorr_lag1": r.autocorr(lag=1),
                "abs_ret_autocorr_lag1": r.abs().autocorr(lag=1),
                "abs_ret_autocorr_lag5": r.abs().autocorr(lag=5),
            }
        )
    autocorr = pd.DataFrame(autocorr_rows)
    autocorr.to_csv(out_dir / "single_stock_autocorr.csv", index=False)

    market = stocks.groupby("date", sort=True)["log_ret_1d"].mean().rename("market_log_ret").to_frame()
    market["market_abs_ret"] = market["market_log_ret"].abs()
    market["market_realized_vol_20d"] = market["market_log_ret"].rolling(20).std() * math.sqrt(252)
    market.to_csv(out_dir / "market_return_volatility.csv")

    merged = stocks[["date", "symbol", "raw_price_level", "close_lag1", "log_ret_1d"]].merge(
        targets[
            [
                "date",
                "symbol",
                "target_ret_fwd_1d",
                "target_excess_market_fwd_1d",
                "target_rank_fwd_1d",
                "target_excess_sector_fwd_1d",
            ]
        ],
        on=["date", "symbol"],
        how="inner",
    )
    raw_price_ic = []
    for score in ["raw_price_level", "close_lag1", "log_ret_1d"]:
        for target in [
            "target_ret_fwd_1d",
            "target_excess_market_fwd_1d",
            "target_rank_fwd_1d",
            "target_excess_sector_fwd_1d",
        ]:
            ic = spearman_by_date(merged, score, target, args.min_names_per_date)
            ic.to_csv(out_dir / f"{score}__{target}__rank_ic.csv", index=False)
            vals = ic["rank_ic"].dropna()
            raw_price_ic.append(
                {
                    "score": score,
                    "target": target,
                    "mean_rank_ic": float(vals.mean()) if len(vals) else None,
                    "rank_ic_std": float(vals.std(ddof=1)) if len(vals) else None,
                    "rank_ic_ir": float(vals.mean() / (vals.std(ddof=1) + 1e-12) * math.sqrt(252))
                    if len(vals)
                    else None,
                    "dates": int(len(vals)),
                }
            )
    raw_price_ic_df = pd.DataFrame(raw_price_ic)
    raw_price_ic_df.to_csv(out_dir / "raw_price_predictability.csv", index=False)

    summary = {
        "data_quality": data_quality,
        "return_diagnostics": return_diag,
        "single_stock_autocorr": {
            "symbols": int(len(autocorr)),
            "mean_ret_autocorr_lag1": safe_stat(autocorr["ret_autocorr_lag1"], "mean"),
            "median_ret_autocorr_lag1": safe_stat(autocorr["ret_autocorr_lag1"], "median"),
            "mean_abs_ret_autocorr_lag1": safe_stat(autocorr["abs_ret_autocorr_lag1"], "mean"),
            "median_abs_ret_autocorr_lag1": safe_stat(autocorr["abs_ret_autocorr_lag1"], "median"),
            "mean_abs_ret_autocorr_lag5": safe_stat(autocorr["abs_ret_autocorr_lag5"], "mean"),
        },
        "market_volatility_clustering": {
            "market_abs_ret_autocorr_lag1": float(market["market_abs_ret"].dropna().autocorr(lag=1)),
            "market_abs_ret_autocorr_lag5": float(market["market_abs_ret"].dropna().autocorr(lag=5)),
            "market_realized_vol_20d_autocorr_lag1": float(
                market["market_realized_vol_20d"].dropna().autocorr(lag=1)
            ),
            "market_realized_vol_20d_autocorr_lag5": float(
                market["market_realized_vol_20d"].dropna().autocorr(lag=5)
            ),
        },
        "raw_price_predictability_topline": raw_price_ic_df.to_dict(orient="records"),
    }
    (out_dir / "diagnostics_summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8"
    )

    lines = [
        "# Research Diagnostics",
        "",
        "## Data Cleanliness",
        "",
        f"- Rows: {data_quality['rows']:,}",
        f"- Symbols: {data_quality['symbols']}",
        f"- Date range: {data_quality['date_min']} to {data_quality['date_max']}",
        f"- Duplicate date-symbol rows: {data_quality['duplicate_symbol_dates']}",
        f"- Non-positive close rows: {data_quality['non_positive_close_rows']}",
        f"- Non-positive volume rows: {data_quality['non_positive_volume_rows']}",
        f"- OHLC inversion rows: {data_quality['ohlc_inversion_rows']}",
        "",
        "## Return Diagnostics",
        "",
        f"- Simple return std: {return_diag['simple_return']['std']:.6f}",
        f"- Log return std: {return_diag['log_return']['std']:.6f}",
        f"- Mean absolute simple-vs-log difference: {return_diag['simple_minus_log_abs_mean']:.8f}",
        f"- 5D log additivity max absolute difference: {return_diag['log_additivity_example']['max_abs_diff_sum_vs_direct_5d']:.12f}",
        "",
        "## Autocorrelation",
        "",
        f"- Mean single-stock lag-1 return autocorrelation: {summary['single_stock_autocorr']['mean_ret_autocorr_lag1']:.4f}",
        f"- Mean single-stock lag-1 absolute-return autocorrelation: {summary['single_stock_autocorr']['mean_abs_ret_autocorr_lag1']:.4f}",
        f"- Market lag-1 absolute-return autocorrelation: {summary['market_volatility_clustering']['market_abs_ret_autocorr_lag1']:.4f}",
        f"- Market 20D realized-vol lag-1 autocorrelation: {summary['market_volatility_clustering']['market_realized_vol_20d_autocorr_lag1']:.4f}",
        "",
        "## Raw Price Predictability",
        "",
        raw_price_ic_df.to_markdown(index=False, floatfmt=".4f"),
    ]
    (out_dir / "diagnostics_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Done. Diagnostics written to {out_dir}")


if __name__ == "__main__":
    main()
