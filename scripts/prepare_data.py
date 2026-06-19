#!/usr/bin/env python3
"""Convert raw Kaggle CSV files into typed Parquet files.

This is a one-time IO optimization step. It keeps the dataset content unchanged
but avoids repeated CSV parsing and stores numeric columns as float32 and core
categoricals as pandas categories.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


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


def prepare_stocks(path: str | Path) -> pd.DataFrame:
    header = pd.read_csv(path, nrows=0).columns.tolist()
    numeric_cols = [c for c in ["open", "high", "low", "close", "adj_close", "volume"] if c in header]
    stocks = pd.read_csv(
        path,
        usecols=["date", "symbol", *numeric_cols],
        dtype={col: "float32" for col in numeric_cols},
        parse_dates=["date"],
    )
    stocks["symbol"] = clean_symbol(stocks["symbol"]).astype("category")
    stocks = stocks.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)
    return stocks


def prepare_companies(path: str | Path) -> pd.DataFrame:
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
    companies["symbol"] = clean_symbol(companies["symbol"])
    for col in ["symbol", "sector", "sub_industry", "headquarters"]:
        companies[col] = companies[col].fillna("Unknown").astype("category")
    return companies


def main() -> None:
    args = parse_args()
    stocks = prepare_stocks(args.stocks_csv)
    companies = prepare_companies(args.companies_csv)
    write_parquet(stocks, args.stocks_out, args.compression)
    write_parquet(companies, args.companies_out, args.compression)

    metadata = {
        "stocks_rows": int(len(stocks)),
        "stocks_symbols": int(stocks["symbol"].nunique()),
        "stocks_date_min": str(stocks["date"].min().date()),
        "stocks_date_max": str(stocks["date"].max().date()),
        "stocks_dtypes": {col: str(dtype) for col, dtype in stocks.dtypes.items()},
        "companies_rows": int(len(companies)),
        "companies_symbols": int(companies["symbol"].nunique()),
        "companies_dtypes": {col: str(dtype) for col, dtype in companies.dtypes.items()},
        "stocks_out": str(args.stocks_out),
        "companies_out": str(args.companies_out),
    }
    metadata_path = Path(args.metadata)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
