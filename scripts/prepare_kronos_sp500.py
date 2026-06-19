#!/usr/bin/env python3
"""Prepare S&P 500 daily OHLCV data for Kronos fine-tuning.

The official Kronos `finetune/` dataset expects pickle files shaped as:

    {
        "AAPL": DataFrame(index=datetime, columns=["open", "high", "low", "close", "vol", "amt"]),
        ...
    }

This script converts the Kaggle-style `sp500_stocks.csv` file in data/raw into
that structure. It estimates `amt` as volume times typical OHLC price because
the raw file does not include traded amount.
"""

from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import pandas as pd


FEATURE_COLUMNS = ["open", "high", "low", "close", "vol", "amt"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stocks-csv", default="data/raw/sp500_stocks.csv")
    parser.add_argument("--out-dir", default="data/kronos/sp500_daily")
    parser.add_argument("--lookback-window", type=int, default=512)
    parser.add_argument("--predict-window", type=int, default=20)
    parser.add_argument("--min-history", type=int, default=None)
    parser.add_argument("--train-start", default="2000-01-03")
    parser.add_argument("--train-end", default="2018-12-31")
    parser.add_argument("--val-start", default="2019-01-01")
    parser.add_argument("--val-end", default="2020-12-31")
    parser.add_argument("--test-start", default="2021-01-01")
    parser.add_argument("--test-end", default=None)
    parser.add_argument("--max-symbols", type=int, default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print metadata without writing pickle files.",
    )
    return parser.parse_args()


def load_stocks(path: str | Path, max_symbols: int | None) -> pd.DataFrame:
    usecols = ["date", "open", "high", "low", "close", "volume", "symbol"]
    stocks = pd.read_csv(
        path,
        usecols=usecols,
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
    stocks = stocks.dropna(subset=usecols)
    stocks = stocks.sort_values(["symbol", "date"], kind="mergesort")
    stocks = stocks.drop_duplicates(["symbol", "date"], keep="last")

    if max_symbols is not None:
        symbols = sorted(stocks["symbol"].unique())[:max_symbols]
        stocks = stocks.loc[stocks["symbol"].isin(symbols)].copy()

    typical_price = stocks[["open", "high", "low", "close"]].mean(axis=1)
    stocks["vol"] = stocks["volume"]
    stocks["amt"] = stocks["vol"] * typical_price
    return stocks


def build_split(
    stocks: pd.DataFrame,
    start: str,
    end: str | None,
    min_window: int,
) -> dict[str, pd.DataFrame]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) if end else stocks["date"].max()
    split: dict[str, pd.DataFrame] = {}

    for symbol, group in stocks.groupby("symbol", sort=True):
        window = group.loc[(group["date"] >= start_ts) & (group["date"] <= end_ts)].copy()
        if len(window) < min_window:
            continue
        window = window.set_index("date")
        window.index.name = "datetime"
        split[str(symbol)] = window[FEATURE_COLUMNS].astype("float32")

    return split


def split_metadata(split: dict[str, pd.DataFrame]) -> dict[str, object]:
    if not split:
        return {"symbols": 0, "rows": 0, "date_min": None, "date_max": None}

    rows = sum(len(df) for df in split.values())
    date_min = min(df.index.min() for df in split.values())
    date_max = max(df.index.max() for df in split.values())
    lengths = pd.Series({symbol: len(df) for symbol, df in split.items()})
    return {
        "symbols": int(len(split)),
        "rows": int(rows),
        "date_min": str(date_min.date()),
        "date_max": str(date_max.date()),
        "min_rows_per_symbol": int(lengths.min()),
        "median_rows_per_symbol": int(lengths.median()),
        "max_rows_per_symbol": int(lengths.max()),
    }


def write_pickle(obj: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)


def main() -> None:
    args = parse_args()
    min_window = args.min_history or args.lookback_window + args.predict_window + 1
    stocks = load_stocks(args.stocks_csv, args.max_symbols)

    splits = {
        "train": build_split(stocks, args.train_start, args.train_end, min_window),
        "val": build_split(stocks, args.val_start, args.val_end, min_window),
        "test": build_split(stocks, args.test_start, args.test_end, min_window),
    }

    metadata = {
        "source": args.stocks_csv,
        "out_dir": args.out_dir,
        "lookback_window": args.lookback_window,
        "predict_window": args.predict_window,
        "min_window": min_window,
        "amount_definition": "volume * mean(open, high, low, close)",
        "raw_rows": int(len(stocks)),
        "raw_symbols": int(stocks["symbol"].nunique()),
        "raw_date_min": str(stocks["date"].min().date()),
        "raw_date_max": str(stocks["date"].max().date()),
        "splits": {name: split_metadata(split) for name, split in splits.items()},
    }

    if not args.dry_run:
        out_dir = Path(args.out_dir)
        write_pickle(splits["train"], out_dir / "train_data.pkl")
        write_pickle(splits["val"], out_dir / "val_data.pkl")
        write_pickle(splits["test"], out_dir / "test_data.pkl")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
