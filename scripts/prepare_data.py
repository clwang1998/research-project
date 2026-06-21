#!/usr/bin/env python3
"""Clean raw Kaggle CSV files and convert them into typed Parquet files.

This is a one-time data preparation step. It normalizes ticker strings, removes
unusable OHLCV rows, de-duplicates symbol/date observations, writes typed
Parquet files, and records a cleaning audit in JSON metadata.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


PRICE_COLS = ["open", "high", "low", "close"]
CORE_STOCK_COLS = ["date", "symbol", *PRICE_COLS, "volume"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stocks-csv", default="data/raw/sp500_stocks.csv")
    parser.add_argument("--companies-csv", default="data/raw/sp500_companies.csv")
    parser.add_argument("--stocks-out", default="data/interim/sp500_stocks_typed.parquet")
    parser.add_argument(
        "--companies-out", default="data/interim/sp500_companies_typed.parquet"
    )
    parser.add_argument("--metadata", default="data/interim/prepare_data_metadata.json")
    parser.add_argument("--compression", default="zstd")
    parser.add_argument(
        "--max-abs-return",
        type=float,
        default=3.0,
        help=(
            "Drop stock-day rows whose one-day simple return exceeds this "
            "absolute threshold after basic OHLCV cleaning; set <=0 to disable."
        ),
    )
    parser.add_argument(
        "--audit-abs-return",
        type=float,
        default=0.5,
        help="Report, but do not necessarily drop, rows above this absolute return.",
    )
    return parser.parse_args()


def clean_symbol(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().str.upper()


def write_parquet(df: pd.DataFrame, path: str | Path, compression: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(path, index=False, compression=compression)
    except Exception:
        if compression == "snappy":
            raise
        df.to_parquet(path, index=False, compression="snappy")


def summarize_stock_quality(stocks: pd.DataFrame) -> dict[str, object]:
    available_price_cols = [c for c in PRICE_COLS if c in stocks.columns]
    summary: dict[str, object] = {
        "rows": int(len(stocks)),
        "symbols": int(stocks["symbol"].nunique()) if "symbol" in stocks.columns else 0,
        "duplicate_symbol_dates": int(stocks.duplicated(["date", "symbol"]).sum())
        if {"date", "symbol"}.issubset(stocks.columns)
        else None,
        "missing_by_column": {
            c: int(stocks[c].isna().sum())
            for c in ["date", "symbol", *available_price_cols, "volume"]
            if c in stocks.columns
        },
        "non_positive_by_column": {
            c: int((stocks[c] <= 0).sum())
            for c in [*available_price_cols, "volume"]
            if c in stocks.columns
        },
    }
    if {"open", "high", "low", "close"}.issubset(stocks.columns):
        high_too_low = stocks["high"] < stocks[["open", "low", "close"]].max(axis=1)
        low_too_high = stocks["low"] > stocks[["open", "high", "close"]].min(axis=1)
        summary["ohlc_inversion_rows"] = int((high_too_low | low_too_high).sum())
    return summary


def clean_stocks(
    stocks: pd.DataFrame,
    price_col: str,
    max_abs_return: float,
    audit_abs_return: float,
) -> tuple[pd.DataFrame, dict[str, object]]:
    audit: dict[str, object] = {
        "raw_rows": int(len(stocks)),
        "raw_quality": summarize_stock_quality(stocks),
        "cleaning_rules": {
            "drop_missing_core_ohlcv": True,
            "drop_duplicate_symbol_date": "keep_last_after_sort",
            "drop_non_positive_prices": True,
            "drop_non_positive_volume": True,
            "drop_ohlc_inversions": True,
            "max_abs_return": max_abs_return,
            "audit_abs_return": audit_abs_return,
        },
    }

    stocks = stocks.dropna(subset=[c for c in CORE_STOCK_COLS if c in stocks.columns]).copy()
    audit["dropped_missing_core_ohlcv"] = int(audit["raw_rows"] - len(stocks))

    before = len(stocks)
    stocks = stocks.sort_values(["symbol", "date"], kind="mergesort")
    stocks = stocks.drop_duplicates(["symbol", "date"], keep="last").copy()
    audit["dropped_duplicate_symbol_dates"] = int(before - len(stocks))

    before = len(stocks)
    positive_cols = [c for c in [*PRICE_COLS, "volume", "adj_close"] if c in stocks.columns]
    positive_mask = pd.Series(True, index=stocks.index)
    for col in positive_cols:
        positive_mask &= stocks[col] > 0
    stocks = stocks.loc[positive_mask].copy()
    audit["dropped_non_positive_ohlcv"] = int(before - len(stocks))

    before = len(stocks)
    high_too_low = stocks["high"] < stocks[["open", "low", "close"]].max(axis=1)
    low_too_high = stocks["low"] > stocks[["open", "high", "close"]].min(axis=1)
    stocks = stocks.loc[~(high_too_low | low_too_high)].copy()
    audit["dropped_ohlc_inversions"] = int(before - len(stocks))

    stocks = stocks.sort_values(["symbol", "date"], kind="mergesort")
    returns = stocks.groupby("symbol", sort=False)[price_col].pct_change()
    audit["abs_return_gt_audit_threshold_rows"] = int((returns.abs() > audit_abs_return).sum())
    if max_abs_return and max_abs_return > 0:
        before = len(stocks)
        stocks = stocks.loc[~(returns.abs() > max_abs_return)].copy()
        audit["dropped_abs_return_gt_max_threshold"] = int(before - len(stocks))
    else:
        audit["dropped_abs_return_gt_max_threshold"] = 0

    stocks = stocks.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)
    audit["clean_rows"] = int(len(stocks))
    audit["rows_dropped_total"] = int(audit["raw_rows"] - len(stocks))
    audit["clean_quality"] = summarize_stock_quality(stocks)
    return stocks, audit


def prepare_stocks(
    path: str | Path,
    max_abs_return: float,
    audit_abs_return: float,
) -> tuple[pd.DataFrame, dict[str, object]]:
    header = pd.read_csv(path, nrows=0).columns.tolist()
    numeric_cols = [c for c in ["open", "high", "low", "close", "adj_close", "volume"] if c in header]
    if not set(CORE_STOCK_COLS).issubset(header):
        missing = sorted(set(CORE_STOCK_COLS) - set(header))
        raise ValueError(f"stocks CSV is missing required columns: {missing}")
    stocks = pd.read_csv(
        path,
        usecols=["date", "symbol", *numeric_cols],
        dtype={col: "float32" for col in numeric_cols},
        parse_dates=["date"],
    )
    stocks["symbol"] = clean_symbol(stocks["symbol"])
    price_col = "adj_close" if "adj_close" in stocks.columns else "close"
    stocks, audit = clean_stocks(stocks, price_col, max_abs_return, audit_abs_return)
    stocks["symbol"] = stocks["symbol"].astype("category")
    return stocks, audit


def prepare_companies(path: str | Path) -> tuple[pd.DataFrame, dict[str, object]]:
    companies = pd.read_csv(
        path,
        dtype={
            "symbol": "string",
            "company": "string",
            "sector": "string",
            "sub_industry": "string",
            "headquarters": "string",
            "founded": "string",
        },
        parse_dates=["date_added"],
    )
    raw_rows = len(companies)
    companies["symbol"] = clean_symbol(companies["symbol"])
    companies = companies.dropna(subset=["symbol"]).sort_values("symbol", kind="mergesort")
    companies = companies.drop_duplicates("symbol", keep="last").copy()
    for col in ["sector", "sub_industry", "headquarters"]:
        companies[col] = companies[col].fillna("Unknown").astype("category")
    companies["symbol"] = companies["symbol"].astype("category")
    audit = {
        "raw_rows": int(raw_rows),
        "clean_rows": int(len(companies)),
        "rows_dropped_total": int(raw_rows - len(companies)),
        "symbols": int(companies["symbol"].nunique()),
        "unknown_counts": {
            col: int((companies[col].astype(str) == "Unknown").sum())
            for col in ["sector", "sub_industry", "headquarters"]
        },
    }
    return companies, audit


def main() -> None:
    args = parse_args()
    stocks, stocks_audit = prepare_stocks(
        args.stocks_csv,
        max_abs_return=args.max_abs_return,
        audit_abs_return=args.audit_abs_return,
    )
    companies, companies_audit = prepare_companies(args.companies_csv)
    write_parquet(stocks, args.stocks_out, args.compression)
    write_parquet(companies, args.companies_out, args.compression)

    metadata = {
        "stocks_rows": int(len(stocks)),
        "stocks_symbols": int(stocks["symbol"].nunique()),
        "stocks_date_min": str(stocks["date"].min().date()),
        "stocks_date_max": str(stocks["date"].max().date()),
        "stocks_dtypes": {col: str(dtype) for col, dtype in stocks.dtypes.items()},
        "stocks_cleaning_audit": stocks_audit,
        "companies_rows": int(len(companies)),
        "companies_symbols": int(companies["symbol"].nunique()),
        "companies_dtypes": {col: str(dtype) for col, dtype in companies.dtypes.items()},
        "companies_cleaning_audit": companies_audit,
        "stocks_out": str(args.stocks_out),
        "companies_out": str(args.companies_out),
    }
    metadata_path = Path(args.metadata)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
