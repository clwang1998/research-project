#!/usr/bin/env python3
"""Build no-external-data S&P 500 equity features.

Inputs:
  - data/interim/sp500_stocks_typed.parquet, or data/raw/sp500_stocks.csv
  - data/interim/sp500_companies_typed.parquet, or data/raw/sp500_companies.csv

The pipeline intentionally uses only OHLCV and company metadata included in the
Kaggle dataset. It creates point-in-time technical, cross-sectional, industry,
peer, geography, and metadata features plus forward-return targets.
"""

from __future__ import annotations

import argparse
import json
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

warnings.simplefilter("ignore", pd.errors.PerformanceWarning)


RETURN_WINDOWS = [1, 2, 3, 5, 10, 20, 40, 60, 120, 252]
VOL_WINDOWS = [5, 10, 20, 40, 60, 120]
MA_WINDOWS = [5, 10, 20, 50, 100, 200]
EMA_WINDOWS = [5, 10, 20, 50, 100, 200]
RSI_WINDOWS = [6, 14, 28]
BOLL_WINDOWS = [20, 60]
CHANNEL_WINDOWS = [20, 60, 120]
TARGET_WINDOWS = [1, 5, 20, 30, 40, 50, 60, 70, 80, 90]

US_STATE_TO_REGION = {
    "Alabama": "South",
    "Alaska": "West",
    "Arizona": "West",
    "Arkansas": "South",
    "California": "West",
    "Colorado": "West",
    "Connecticut": "Northeast",
    "Delaware": "South",
    "Florida": "South",
    "Georgia": "South",
    "Hawaii": "West",
    "Idaho": "West",
    "Illinois": "Midwest",
    "Indiana": "Midwest",
    "Iowa": "Midwest",
    "Kansas": "Midwest",
    "Kentucky": "South",
    "Louisiana": "South",
    "Maine": "Northeast",
    "Maryland": "South",
    "Massachusetts": "Northeast",
    "Michigan": "Midwest",
    "Minnesota": "Midwest",
    "Mississippi": "South",
    "Missouri": "Midwest",
    "Montana": "West",
    "Nebraska": "Midwest",
    "Nevada": "West",
    "New Hampshire": "Northeast",
    "New Jersey": "Northeast",
    "New Mexico": "West",
    "New York": "Northeast",
    "North Carolina": "South",
    "North Dakota": "Midwest",
    "Ohio": "Midwest",
    "Oklahoma": "South",
    "Oregon": "West",
    "Pennsylvania": "Northeast",
    "Rhode Island": "Northeast",
    "South Carolina": "South",
    "South Dakota": "Midwest",
    "Tennessee": "South",
    "Texas": "South",
    "Utah": "West",
    "Vermont": "Northeast",
    "Virginia": "South",
    "Washington": "West",
    "West Virginia": "South",
    "Wisconsin": "Midwest",
    "Wyoming": "West",
}


@dataclass
class FeatureManifest:
    rows: list[dict[str, str]]

    def add(self, name: str, category: str, description: str) -> None:
        self.rows.append(
            {"feature": name, "category": category, "description": description}
        )

    def add_many(
        self, names: Iterable[str], category: str, description_template: str
    ) -> None:
        for name in names:
            self.add(name, category, description_template.format(feature=name))

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows).drop_duplicates("feature")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stocks", default="data/interim/sp500_stocks_typed.parquet")
    parser.add_argument("--companies", default="data/interim/sp500_companies_typed.parquet")
    parser.add_argument("--out", default="data/processed/sp500_features.parquet")
    parser.add_argument("--manifest", default="data/processed/feature_manifest.csv")
    parser.add_argument("--metadata", default="data/processed/feature_build_metadata.json")
    parser.add_argument("--sample-csv", default="data/processed/sp500_features_sample.csv")
    parser.add_argument("--max-symbols", type=int, default=None)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--min-history-days", type=int, default=0)
    parser.add_argument("--sample-rows", type=int, default=5000)
    parser.add_argument(
        "--no-pickle",
        dest="no_output",
        action="store_true",
        help="Skip full feature output; useful for quick smoke tests.",
    )
    parser.add_argument(
        "--no-output",
        dest="no_output",
        action="store_true",
        help="Skip full feature output; useful for quick smoke tests.",
    )
    return parser.parse_args()


def safe_div(num: pd.Series | np.ndarray, den: pd.Series | np.ndarray) -> pd.Series:
    return pd.Series(num).div(pd.Series(den).replace(0, np.nan))


def infer_price_col(columns: Iterable[str]) -> str:
    cols = set(columns)
    return "adj_close" if "adj_close" in cols else "close"


def clean_symbol(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.upper()


def extract_years(value: object) -> list[int]:
    years = [int(x) for x in re.findall(r"(?:18|19|20)\d{2}", str(value))]
    return years


def parse_headquarters(value: object) -> tuple[str, str, str]:
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return "Unknown", "Unknown", "Unknown"
    parts = [p.strip() for p in text.split(",") if p.strip()]
    city = parts[0] if parts else "Unknown"
    state_or_country = parts[-1] if len(parts) >= 2 else "Unknown"
    region = US_STATE_TO_REGION.get(state_or_country, "Non-US")
    if state_or_country == "Unknown":
        region = "Unknown"
    return city, state_or_country, region


def load_inputs(
    stocks_path: str | Path,
    companies_path: str | Path,
    max_symbols: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    min_history_days: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    stocks_path = Path(stocks_path)
    companies_path = Path(companies_path)
    if stocks_path.suffix == ".parquet":
        stocks = pd.read_parquet(stocks_path)
        price_col = infer_price_col(stocks.columns)
        usecols = ["date", "open", "high", "low", "close", "volume", "symbol"]
        if price_col == "adj_close":
            usecols.append("adj_close")
        stocks = stocks.loc[:, usecols]
    else:
        stocks_head = pd.read_csv(stocks_path, nrows=1)
        price_col = infer_price_col(stocks_head.columns)
        usecols = ["date", "open", "high", "low", "close", "volume", "symbol"]
        if price_col == "adj_close":
            usecols.append("adj_close")
        numeric_cols = [c for c in usecols if c not in ["date", "symbol"]]
        stocks = pd.read_csv(
            stocks_path,
            usecols=usecols,
            dtype={col: "float32" for col in numeric_cols},
            parse_dates=["date"],
        )

    if stocks["date"].dtype == "object":
        stocks["date"] = pd.to_datetime(stocks["date"])
    stocks["symbol"] = clean_symbol(stocks["symbol"]).astype("category")

    if companies_path.suffix == ".parquet":
        companies = pd.read_parquet(companies_path)
    else:
        companies = pd.read_csv(companies_path)
    companies["symbol"] = clean_symbol(companies["symbol"])

    if start_date:
        stocks = stocks.loc[stocks["date"] >= pd.Timestamp(start_date)]
    if end_date:
        stocks = stocks.loc[stocks["date"] <= pd.Timestamp(end_date)]

    if min_history_days > 0:
        counts = stocks.groupby("symbol")["date"].transform("count")
        stocks = stocks.loc[counts >= min_history_days].copy()

    if max_symbols:
        symbols = sorted(stocks["symbol"].unique())[:max_symbols]
        stocks = stocks.loc[stocks["symbol"].isin(symbols)].copy()

    return stocks, companies, price_col


def prepare_metadata(companies: pd.DataFrame) -> pd.DataFrame:
    companies = companies.copy()
    companies["sector"] = companies["sector"].astype("string").fillna("Unknown").astype(str)
    companies["sub_industry"] = (
        companies["sub_industry"].astype("string").fillna("Unknown").astype(str)
    )
    companies["company"] = companies["company"].astype("string").fillna("Unknown").astype(str)
    companies["date_added"] = pd.to_datetime(companies["date_added"], errors="coerce")

    years = companies["founded"].map(extract_years)
    companies["founded_year"] = years.map(lambda xs: xs[0] if xs else np.nan)
    companies["legacy_founded_year"] = years.map(lambda xs: min(xs) if xs else np.nan)

    hq = companies["headquarters"].astype("string").map(parse_headquarters)
    companies["hq_city"] = [x[0] for x in hq]
    companies["hq_state"] = [x[1] for x in hq]
    companies["hq_region"] = [x[2] for x in hq]

    for col in ["sector", "sub_industry", "hq_city", "hq_state", "hq_region"]:
        companies[f"{col}_code"] = pd.Categorical(companies[col]).codes.astype("int16")
        companies[f"{col}_n_companies"] = companies.groupby(col)["symbol"].transform(
            "count"
        )

    keep = [
        "symbol",
        "company",
        "sector",
        "sub_industry",
        "date_added",
        "founded_year",
        "legacy_founded_year",
        "hq_city",
        "hq_state",
        "hq_region",
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
    ]
    return companies[keep]


def add_calendar_and_metadata_features(df: pd.DataFrame, manifest: FeatureManifest) -> None:
    df["year"] = df["date"].dt.year.astype("int16")
    df["month"] = df["date"].dt.month.astype("int8")
    df["quarter"] = df["date"].dt.quarter.astype("int8")
    df["day_of_week"] = df["date"].dt.dayofweek.astype("int8")
    df["is_month_end"] = df["date"].dt.is_month_end.astype("int8")
    df["is_quarter_end"] = df["date"].dt.is_quarter_end.astype("int8")
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

    first_trade = df.groupby("symbol")["date"].transform("min")
    df["first_trade_age_years"] = (df["date"] - first_trade).dt.days / 365.25
    df["firm_age_years"] = df["year"] - df["founded_year"]
    df["legacy_firm_age_years"] = df["year"] - df["legacy_founded_year"]
    date_added = df["date_added"]
    member_age = (df["date"] - date_added).dt.days / 365.25
    df["sp500_membership_age_years"] = member_age.where(df["date"] >= date_added)
    df["sp500_member_asof"] = (df["date"] >= date_added).astype("int8")

    manifest.add_many(
        [
            "year",
            "month",
            "quarter",
            "day_of_week",
            "is_month_end",
            "is_quarter_end",
            "month_sin",
            "month_cos",
        ],
        "calendar",
        "{feature}: calendar timing feature.",
    )
    manifest.add_many(
        [
            "first_trade_age_years",
            "firm_age_years",
            "legacy_firm_age_years",
            "sp500_membership_age_years",
            "sp500_member_asof",
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
        ],
        "metadata",
        "{feature}: company metadata feature from sp500_companies.csv.",
    )


def add_price_return_features(
    df: pd.DataFrame, price_col: str, manifest: FeatureManifest
) -> None:
    g = df.groupby("symbol", sort=False)
    log_price = np.log(df[price_col].clip(lower=1e-12))
    df["log_price"] = log_price
    df["dollar_volume"] = df[price_col] * df["volume"]
    df["log_volume"] = np.log1p(df["volume"].clip(lower=0))
    df["log_dollar_volume"] = np.log1p(df["dollar_volume"].clip(lower=0))

    prev_close = g[price_col].shift(1)
    df["intraday_ret"] = df["close"] / df["open"].replace(0, np.nan) - 1
    df["overnight_ret"] = df["open"] / prev_close.replace(0, np.nan) - 1
    df["high_low_range"] = df["high"] / df["low"].replace(0, np.nan) - 1
    df["close_location"] = (df["close"] - df["low"]) / (
        df["high"] - df["low"]
    ).replace(0, np.nan)
    df["open_location"] = (df["open"] - df["low"]) / (
        df["high"] - df["low"]
    ).replace(0, np.nan)
    df["close_to_high"] = df["close"] / df["high"].replace(0, np.nan) - 1
    df["close_to_low"] = df["close"] / df["low"].replace(0, np.nan) - 1

    for w in RETURN_WINDOWS:
        df[f"ret_{w}d"] = g[price_col].pct_change(w)
        df[f"log_ret_{w}d"] = g["log_price"].diff(w)
        df[f"rev_{w}d"] = -df[f"ret_{w}d"]

    skip_pairs = [(5, 20), (20, 60), (20, 120), (21, 252)]
    for skip, lookback in skip_pairs:
        df[f"mom_{lookback}d_skip_{skip}d"] = (
            g[price_col].shift(skip) / g[price_col].shift(lookback) - 1
        )

    for short, long in [(5, 20), (10, 40), (20, 60), (60, 120), (120, 252)]:
        df[f"mom_accel_{short}_{long}"] = df[f"ret_{short}d"] - df[f"ret_{long}d"]

    manifest.add_many(
        [
            "log_price",
            "dollar_volume",
            "log_volume",
            "log_dollar_volume",
            "intraday_ret",
            "overnight_ret",
            "high_low_range",
            "close_location",
            "open_location",
            "close_to_high",
            "close_to_low",
        ],
        "price_return",
        "{feature}: raw OHLCV-derived price/volume state.",
    )
    manifest.add_many(
        [f"ret_{w}d" for w in RETURN_WINDOWS]
        + [f"log_ret_{w}d" for w in RETURN_WINDOWS]
        + [f"rev_{w}d" for w in RETURN_WINDOWS]
        + [f"mom_{lookback}d_skip_{skip}d" for skip, lookback in skip_pairs]
        + [
            f"mom_accel_{short}_{long}"
            for short, long in [(5, 20), (10, 40), (20, 60), (60, 120), (120, 252)]
        ],
        "momentum_reversal",
        "{feature}: momentum or reversal signal from lagged prices.",
    )


def add_volatility_features(df: pd.DataFrame, manifest: FeatureManifest) -> None:
    g = df.groupby("symbol", sort=False)
    ret = df["ret_1d"]
    log_hl = np.log(df["high"].clip(lower=1e-12) / df["low"].clip(lower=1e-12))
    log_co = np.log(df["close"].clip(lower=1e-12) / df["open"].clip(lower=1e-12))
    parkinson_daily = log_hl.pow(2) / (4 * np.log(2))
    gk_daily = 0.5 * log_hl.pow(2) - (2 * np.log(2) - 1) * log_co.pow(2)
    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - g["close"].shift(1)).abs(),
            (df["low"] - g["close"].shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["true_range_pct"] = true_range / df["close"].replace(0, np.nan)

    for w in VOL_WINDOWS:
        roll_ret = g["ret_1d"].rolling(w, min_periods=max(3, w // 2))
        df[f"vol_{w}d"] = roll_ret.std().reset_index(level=0, drop=True)
        df[f"downside_vol_{w}d"] = (
            ret.where(ret < 0, 0)
            .groupby(df["symbol"], sort=False)
            .rolling(w, min_periods=max(3, w // 2))
            .std()
            .reset_index(level=0, drop=True)
        )
        df[f"upside_vol_{w}d"] = (
            ret.where(ret > 0, 0)
            .groupby(df["symbol"], sort=False)
            .rolling(w, min_periods=max(3, w // 2))
            .std()
            .reset_index(level=0, drop=True)
        )
        df[f"parkinson_vol_{w}d"] = (
            parkinson_daily.groupby(df["symbol"], sort=False)
            .rolling(w, min_periods=max(3, w // 2))
            .mean()
            .reset_index(level=0, drop=True)
            .clip(lower=0)
            .pow(0.5)
        )
        df[f"gk_vol_{w}d"] = (
            gk_daily.groupby(df["symbol"], sort=False)
            .rolling(w, min_periods=max(3, w // 2))
            .mean()
            .reset_index(level=0, drop=True)
            .clip(lower=0)
            .pow(0.5)
        )
        df[f"atr_{w}d"] = (
            df["true_range_pct"]
            .groupby(df["symbol"], sort=False)
            .rolling(w, min_periods=max(3, w // 2))
            .mean()
            .reset_index(level=0, drop=True)
        )
        df[f"ret_skew_{w}d"] = roll_ret.skew().reset_index(level=0, drop=True)
        df[f"ret_kurt_{w}d"] = roll_ret.kurt().reset_index(level=0, drop=True)
        df[f"max_ret_{w}d"] = roll_ret.max().reset_index(level=0, drop=True)
        df[f"min_ret_{w}d"] = roll_ret.min().reset_index(level=0, drop=True)

    for short, long in [(5, 20), (10, 40), (20, 60), (60, 120)]:
        df[f"vol_ratio_{short}_{long}"] = df[f"vol_{short}d"] / df[
            f"vol_{long}d"
        ].replace(0, np.nan)

    for w in [20, 60, 120, 252]:
        roll_max = g["close"].rolling(w, min_periods=max(5, w // 3)).max()
        df[f"drawdown_from_{w}d_high"] = (
            df["close"].values / roll_max.reset_index(level=0, drop=True) - 1
        )

    manifest.add("true_range_pct", "volatility", "True range normalized by close.")
    manifest.add_many(
        [f"vol_{w}d" for w in VOL_WINDOWS]
        + [f"downside_vol_{w}d" for w in VOL_WINDOWS]
        + [f"upside_vol_{w}d" for w in VOL_WINDOWS]
        + [f"parkinson_vol_{w}d" for w in VOL_WINDOWS]
        + [f"gk_vol_{w}d" for w in VOL_WINDOWS]
        + [f"atr_{w}d" for w in VOL_WINDOWS]
        + [f"ret_skew_{w}d" for w in VOL_WINDOWS]
        + [f"ret_kurt_{w}d" for w in VOL_WINDOWS]
        + [f"max_ret_{w}d" for w in VOL_WINDOWS]
        + [f"min_ret_{w}d" for w in VOL_WINDOWS]
        + [f"vol_ratio_{short}_{long}" for short, long in [(5, 20), (10, 40), (20, 60), (60, 120)]]
        + [f"drawdown_from_{w}d_high" for w in [20, 60, 120, 252]],
        "volatility",
        "{feature}: rolling volatility, tail, range, or drawdown feature.",
    )


def add_trend_features(
    df: pd.DataFrame, price_col: str, manifest: FeatureManifest
) -> None:
    g = df.groupby("symbol", sort=False)
    close = df[price_col]

    for w in MA_WINDOWS:
        ma = g[price_col].rolling(w, min_periods=max(3, w // 2)).mean().reset_index(
            level=0, drop=True
        )
        df[f"sma_{w}d"] = ma
        df[f"sma_gap_{w}d"] = close / ma.replace(0, np.nan) - 1
        df[f"sma_slope_{w}d"] = ma.groupby(df["symbol"], sort=False).pct_change(
            w, fill_method=None
        )

    for w in EMA_WINDOWS:
        ema = g[price_col].transform(lambda s: s.ewm(span=w, adjust=False).mean())
        df[f"ema_{w}d"] = ema
        df[f"ema_gap_{w}d"] = close / ema.replace(0, np.nan) - 1

    ema12 = g[price_col].transform(lambda s: s.ewm(span=12, adjust=False).mean())
    ema26 = g[price_col].transform(lambda s: s.ewm(span=26, adjust=False).mean())
    macd = ema12 - ema26
    macd_signal = macd.groupby(df["symbol"], sort=False).transform(
        lambda s: s.ewm(span=9, adjust=False).mean()
    )
    df["macd_line"] = macd / close.replace(0, np.nan)
    df["macd_signal"] = macd_signal / close.replace(0, np.nan)
    df["macd_hist"] = (macd - macd_signal) / close.replace(0, np.nan)

    delta = g[price_col].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    for w in RSI_WINDOWS:
        avg_gain = (
            gain.groupby(df["symbol"], sort=False)
            .rolling(w, min_periods=max(3, w // 2))
            .mean()
            .reset_index(level=0, drop=True)
        )
        avg_loss = (
            loss.groupby(df["symbol"], sort=False)
            .rolling(w, min_periods=max(3, w // 2))
            .mean()
            .reset_index(level=0, drop=True)
        )
        rs = avg_gain / avg_loss.replace(0, np.nan)
        df[f"rsi_{w}d"] = 100 - 100 / (1 + rs)

    for w in BOLL_WINDOWS:
        mid = g[price_col].rolling(w, min_periods=max(5, w // 2)).mean().reset_index(
            level=0, drop=True
        )
        std = g[price_col].rolling(w, min_periods=max(5, w // 2)).std().reset_index(
            level=0, drop=True
        )
        upper = mid + 2 * std
        lower = mid - 2 * std
        df[f"boll_z_{w}d"] = (close - mid) / std.replace(0, np.nan)
        df[f"boll_bandwidth_{w}d"] = (upper - lower) / mid.replace(0, np.nan)
        df[f"boll_percent_b_{w}d"] = (close - lower) / (upper - lower).replace(
            0, np.nan
        )

    for w in CHANNEL_WINDOWS:
        roll_high = (
            g["high"].rolling(w, min_periods=max(5, w // 2)).max().reset_index(
                level=0, drop=True
            )
        )
        roll_low = (
            g["low"].rolling(w, min_periods=max(5, w // 2)).min().reset_index(
                level=0, drop=True
            )
        )
        df[f"channel_pos_{w}d"] = (close - roll_low) / (roll_high - roll_low).replace(
            0, np.nan
        )
        df[f"breakout_high_{w}d"] = close / roll_high.replace(0, np.nan) - 1
        df[f"breakout_low_{w}d"] = close / roll_low.replace(0, np.nan) - 1
        df[f"williams_r_{w}d"] = -100 * (roll_high - close) / (
            roll_high - roll_low
        ).replace(0, np.nan)

    typical = (df["high"] + df["low"] + df["close"]) / 3
    for w in [20, 60]:
        tp_mean = (
            typical.groupby(df["symbol"], sort=False)
            .rolling(w, min_periods=max(5, w // 2))
            .mean()
            .reset_index(level=0, drop=True)
        )
        tp_std = (
            typical.groupby(df["symbol"], sort=False)
            .rolling(w, min_periods=max(5, w // 2))
            .std()
            .reset_index(level=0, drop=True)
        )
        df[f"cci_approx_{w}d"] = (typical - tp_mean) / (0.015 * tp_std.replace(0, np.nan))

    manifest.add_many(
        [f"sma_{w}d" for w in MA_WINDOWS]
        + [f"sma_gap_{w}d" for w in MA_WINDOWS]
        + [f"sma_slope_{w}d" for w in MA_WINDOWS]
        + [f"ema_{w}d" for w in EMA_WINDOWS]
        + [f"ema_gap_{w}d" for w in EMA_WINDOWS]
        + ["macd_line", "macd_signal", "macd_hist"]
        + [f"rsi_{w}d" for w in RSI_WINDOWS]
        + [f"boll_z_{w}d" for w in BOLL_WINDOWS]
        + [f"boll_bandwidth_{w}d" for w in BOLL_WINDOWS]
        + [f"boll_percent_b_{w}d" for w in BOLL_WINDOWS]
        + [f"channel_pos_{w}d" for w in CHANNEL_WINDOWS]
        + [f"breakout_high_{w}d" for w in CHANNEL_WINDOWS]
        + [f"breakout_low_{w}d" for w in CHANNEL_WINDOWS]
        + [f"williams_r_{w}d" for w in CHANNEL_WINDOWS]
        + [f"cci_approx_{w}d" for w in [20, 60]],
        "trend_technical",
        "{feature}: rolling trend, oscillator, or breakout feature.",
    )


def add_liquidity_features(df: pd.DataFrame, manifest: FeatureManifest) -> None:
    g = df.groupby("symbol", sort=False)
    volume_ret = g["volume"].pct_change()

    for w in [5, 10, 20, 60, 120]:
        vol_mean = (
            g["volume"].rolling(w, min_periods=max(3, w // 2)).mean().reset_index(
                level=0, drop=True
            )
        )
        vol_std = (
            g["volume"].rolling(w, min_periods=max(3, w // 2)).std().reset_index(
                level=0, drop=True
            )
        )
        dollar_mean = (
            g["dollar_volume"]
            .rolling(w, min_periods=max(3, w // 2))
            .mean()
            .reset_index(level=0, drop=True)
        )
        dollar_std = (
            g["dollar_volume"]
            .rolling(w, min_periods=max(3, w // 2))
            .std()
            .reset_index(level=0, drop=True)
        )
        df[f"volume_mean_{w}d"] = vol_mean
        df[f"volume_z_{w}d"] = (df["volume"] - vol_mean) / vol_std.replace(0, np.nan)
        df[f"volume_ratio_{w}d"] = df["volume"] / vol_mean.replace(0, np.nan)
        df[f"dollar_volume_mean_{w}d"] = dollar_mean
        df[f"dollar_volume_z_{w}d"] = (df["dollar_volume"] - dollar_mean) / (
            dollar_std.replace(0, np.nan)
        )
        df[f"volume_mom_{w}d"] = g["volume"].pct_change(w)
        df[f"volume_vol_{w}d"] = (
            volume_ret.groupby(df["symbol"], sort=False)
            .rolling(w, min_periods=max(3, w // 2))
            .std()
            .reset_index(level=0, drop=True)
        )
        amihud_daily = df["ret_1d"].abs() / df["dollar_volume"].replace(0, np.nan)
        df[f"amihud_{w}d"] = (
            amihud_daily.groupby(df["symbol"], sort=False)
            .rolling(w, min_periods=max(3, w // 2))
            .mean()
            .reset_index(level=0, drop=True)
        )

    df["ret_per_log_dollar_volume"] = df["ret_1d"].abs() / df[
        "log_dollar_volume"
    ].replace(0, np.nan)

    manifest.add_many(
        [f"volume_mean_{w}d" for w in [5, 10, 20, 60, 120]]
        + [f"volume_z_{w}d" for w in [5, 10, 20, 60, 120]]
        + [f"volume_ratio_{w}d" for w in [5, 10, 20, 60, 120]]
        + [f"dollar_volume_mean_{w}d" for w in [5, 10, 20, 60, 120]]
        + [f"dollar_volume_z_{w}d" for w in [5, 10, 20, 60, 120]]
        + [f"volume_mom_{w}d" for w in [5, 10, 20, 60, 120]]
        + [f"volume_vol_{w}d" for w in [5, 10, 20, 60, 120]]
        + [f"amihud_{w}d" for w in [5, 10, 20, 60, 120]]
        + ["ret_per_log_dollar_volume"],
        "liquidity_volume",
        "{feature}: volume, dollar-volume, liquidity, or price-impact proxy.",
    )


def _rolling_group_features(
    table: pd.DataFrame,
    keys: list[str],
    prefix: str,
    manifest: FeatureManifest,
) -> pd.DataFrame:
    table = table.sort_values(keys + ["date"]).copy()
    g = table.groupby(keys, sort=False)
    for w in [5, 20, 60]:
        log_ret = np.log1p(table[f"{prefix}_ret_1d"].clip(lower=-0.999))
        table[f"{prefix}_ret_{w}d"] = (
            log_ret.groupby([table[k] for k in keys], sort=False)
            .rolling(w, min_periods=max(3, w // 2))
            .sum()
            .reset_index(level=list(range(len(keys))), drop=True)
            .pipe(np.expm1)
        )
    for w in [20, 60]:
        table[f"{prefix}_vol_{w}d"] = (
            g[f"{prefix}_ret_1d"]
            .rolling(w, min_periods=max(5, w // 2))
            .std()
            .reset_index(level=list(range(len(keys))), drop=True)
        )
        table[f"{prefix}_breadth_{w}d"] = (
            g[f"{prefix}_breadth_1d"]
            .rolling(w, min_periods=max(5, w // 2))
            .mean()
            .reset_index(level=list(range(len(keys))), drop=True)
        )
        table[f"{prefix}_dispersion_{w}d"] = (
            g[f"{prefix}_dispersion_1d"]
            .rolling(w, min_periods=max(5, w // 2))
            .mean()
            .reset_index(level=list(range(len(keys))), drop=True)
        )

    manifest.add_many(
        [f"{prefix}_ret_1d", f"{prefix}_breadth_1d", f"{prefix}_dispersion_1d", f"{prefix}_n_stocks"]
        + [f"{prefix}_ret_{w}d" for w in [5, 20, 60]]
        + [f"{prefix}_vol_{w}d" for w in [20, 60]]
        + [f"{prefix}_breadth_{w}d" for w in [20, 60]]
        + [f"{prefix}_dispersion_{w}d" for w in [20, 60]],
        "industry_peer",
        "{feature}: rolling group-level return, breadth, volatility, or dispersion.",
    )
    return table


def add_market_industry_features(df: pd.DataFrame, manifest: FeatureManifest) -> None:
    up = (df["ret_1d"] > 0).astype(float)
    market = (
        df.groupby("date", sort=False)
        .agg(
            market_ret_1d=("ret_1d", "mean"),
            market_breadth_1d=("ret_1d", lambda x: float((x > 0).mean())),
            market_dispersion_1d=("ret_1d", "std"),
            market_dollar_volume=("dollar_volume", "sum"),
        )
        .reset_index()
        .sort_values("date")
    )
    for w in [5, 20, 60]:
        market[f"market_ret_{w}d"] = np.expm1(
            np.log1p(market["market_ret_1d"].clip(lower=-0.999))
            .rolling(w, min_periods=max(3, w // 2))
            .sum()
        )
    for w in [20, 60]:
        market[f"market_vol_{w}d"] = market["market_ret_1d"].rolling(
            w, min_periods=max(5, w // 2)
        ).std()
        market[f"market_breadth_{w}d"] = market["market_breadth_1d"].rolling(
            w, min_periods=max(5, w // 2)
        ).mean()
        market[f"market_dispersion_{w}d"] = market["market_dispersion_1d"].rolling(
            w, min_periods=max(5, w // 2)
        ).mean()
    mv_mean = market["market_dollar_volume"].rolling(20, min_periods=10).mean()
    mv_std = market["market_dollar_volume"].rolling(20, min_periods=10).std()
    market["market_dollar_volume_z_20d"] = (
        market["market_dollar_volume"] - mv_mean
    ) / mv_std.replace(0, np.nan)
    df.drop(columns=[c for c in market.columns if c in df.columns and c != "date"], errors="ignore", inplace=True)
    df_market = market
    df_tmp = df.merge(df_market, on="date", how="left", sort=False)
    for col in df_tmp.columns:
        if col not in df.columns:
            df[col] = df_tmp[col].values

    for group_col, prefix in [("sector", "sector"), ("sub_industry", "subind")]:
        group_daily = (
            df.groupby(["date", group_col], sort=False)
            .agg(
                **{
                    f"{prefix}_ret_1d": ("ret_1d", "mean"),
                    f"{prefix}_breadth_1d": ("ret_1d", lambda x: float((x > 0).mean())),
                    f"{prefix}_dispersion_1d": ("ret_1d", "std"),
                    f"{prefix}_n_stocks": ("symbol", "count"),
                }
            )
            .reset_index()
        )
        group_daily = _rolling_group_features(group_daily, [group_col], prefix, manifest)
        df_group = group_daily
        df_tmp = df.merge(df_group, on=["date", group_col], how="left", sort=False)
        for col in df_group.columns:
            if col not in ["date", group_col]:
                df[col] = df_tmp[col].values

    for w in [1, 5, 20, 60]:
        source_col = "ret_1d" if w == 1 else f"ret_{w}d"
        if source_col in df.columns:
            df[f"excess_sector_ret_{w}d"] = df[source_col] - df[f"sector_ret_{w}d"]
            df[f"excess_subind_ret_{w}d"] = df[source_col] - df[f"subind_ret_{w}d"]

    for w in [20, 60]:
        df[f"sector_mom_rank_{w}d"] = df.groupby("date", sort=False)[
            f"sector_ret_{w}d"
        ].rank(pct=True)
        df[f"subind_mom_rank_{w}d"] = df.groupby("date", sort=False)[
            f"subind_ret_{w}d"
        ].rank(pct=True)

    manifest.add_many(
        [
            "market_ret_1d",
            "market_breadth_1d",
            "market_dispersion_1d",
            "market_dollar_volume",
            "market_dollar_volume_z_20d",
        ]
        + [f"market_ret_{w}d" for w in [5, 20, 60]]
        + [f"market_vol_{w}d" for w in [20, 60]]
        + [f"market_breadth_{w}d" for w in [20, 60]]
        + [f"market_dispersion_{w}d" for w in [20, 60]],
        "market_regime",
        "{feature}: broad market return, volatility, breadth, liquidity, or dispersion state.",
    )
    manifest.add_many(
        [f"excess_sector_ret_{w}d" for w in [1, 5, 20, 60]]
        + [f"excess_subind_ret_{w}d" for w in [1, 5, 20, 60]]
        + [f"sector_mom_rank_{w}d" for w in [20, 60]]
        + [f"subind_mom_rank_{w}d" for w in [20, 60]],
        "industry_relative",
        "{feature}: stock performance relative to sector/subindustry or group rank.",
    )


def add_beta_and_correlation_features(df: pd.DataFrame, manifest: FeatureManifest) -> None:
    g = df.groupby("symbol", sort=False)
    for w in [60, 120]:
        cov = (
            g[["ret_1d", "market_ret_1d"]]
            .apply(
                lambda x: x["ret_1d"]
                .rolling(w, min_periods=max(20, w // 2))
                .cov(x["market_ret_1d"])
            )
            .reset_index(level=0, drop=True)
        )
        var = (
            df["market_ret_1d"]
            .groupby(df["symbol"], sort=False)
            .rolling(w, min_periods=max(20, w // 2))
            .var()
            .reset_index(level=0, drop=True)
        )
        df[f"beta_{w}d"] = cov / var.replace(0, np.nan)
        df[f"corr_market_{w}d"] = (
            g[["ret_1d", "market_ret_1d"]]
            .apply(
                lambda x: x["ret_1d"]
                .rolling(w, min_periods=max(20, w // 2))
                .corr(x["market_ret_1d"])
            )
            .reset_index(level=0, drop=True)
        )
        df[f"idio_ret_{w}d"] = df["ret_1d"] - df[f"beta_{w}d"] * df["market_ret_1d"]
        df[f"idio_vol_{w}d"] = (
            df[f"idio_ret_{w}d"]
            .groupby(df["symbol"], sort=False)
            .rolling(w, min_periods=max(20, w // 2))
            .std()
            .reset_index(level=0, drop=True)
        )

    manifest.add_many(
        [f"beta_{w}d" for w in [60, 120]]
        + [f"corr_market_{w}d" for w in [60, 120]]
        + [f"idio_ret_{w}d" for w in [60, 120]]
        + [f"idio_vol_{w}d" for w in [60, 120]],
        "statistical_linkage",
        "{feature}: rolling beta, correlation, idiosyncratic return, or idiosyncratic volatility.",
    )


def add_leave_one_out_peer_mean(
    df: pd.DataFrame,
    group_col: str,
    value_col: str,
    out_col: str,
) -> None:
    group = df.groupby(["date", group_col], sort=False)[value_col]
    mean = group.transform("mean")
    count = group.transform("count")
    df[out_col] = (mean * count - df[value_col]) / (count - 1).replace(0, np.nan)


def add_peer_and_style_features(df: pd.DataFrame, manifest: FeatureManifest) -> None:
    peer_cols = [
        "ret_1d",
        "ret_5d",
        "ret_20d",
        "vol_20d",
        "rsi_14d",
        "volume_z_20d",
        "sma_gap_20d",
        "beta_60d",
    ]
    for value_col in peer_cols:
        if value_col not in df.columns:
            continue
        add_leave_one_out_peer_mean(
            df, "sector", value_col, f"sector_peer_mean_{value_col}"
        )
        add_leave_one_out_peer_mean(
            df, "sub_industry", value_col, f"subind_peer_mean_{value_col}"
        )
        df[f"sector_peer_excess_{value_col}"] = df[value_col] - df[
            f"sector_peer_mean_{value_col}"
        ]
        df[f"subind_peer_excess_{value_col}"] = df[value_col] - df[
            f"subind_peer_mean_{value_col}"
        ]

    for group_col, prefix in [("hq_state", "hq_state"), ("hq_region", "hq_region")]:
        hq_daily = (
            df.groupby(["date", group_col], sort=False)
            .agg(
                **{
                    f"{prefix}_ret_1d": ("ret_1d", "mean"),
                    f"{prefix}_breadth_1d": ("ret_1d", lambda x: float((x > 0).mean())),
                    f"{prefix}_n_stocks": ("symbol", "count"),
                }
            )
            .reset_index()
            .sort_values([group_col, "date"])
        )
        hq_daily[f"{prefix}_ret_20d"] = np.expm1(
            np.log1p(hq_daily[f"{prefix}_ret_1d"].clip(lower=-0.999))
            .groupby(hq_daily[group_col], sort=False)
            .rolling(20, min_periods=10)
            .sum()
            .reset_index(level=0, drop=True)
        )
        df_tmp = df.merge(hq_daily, on=["date", group_col], how="left", sort=False)
        for col in hq_daily.columns:
            if col not in ["date", group_col]:
                df[col] = df_tmp[col].values

    # Coarse style buckets: momentum x volatility x liquidity terciles. These are
    # cheap proxies for a style-similarity peer group without external Barra data.
    style_inputs = {
        "style_mom_bucket": "ret_60d",
        "style_vol_bucket": "vol_60d",
        "style_liq_bucket": "log_dollar_volume",
    }
    for out_col, src_col in style_inputs.items():
        rank = df.groupby("date", sort=False)[src_col].rank(pct=True)
        df[out_col] = np.select(
            [rank <= 1 / 3, rank <= 2 / 3], [0, 1], default=2
        ).astype("int8")
    df["style_bucket"] = (
        df["style_mom_bucket"] * 9
        + df["style_vol_bucket"] * 3
        + df["style_liq_bucket"]
    ).astype("int8")

    for value_col in ["ret_1d", "ret_5d", "ret_20d", "vol_20d", "rsi_14d"]:
        add_leave_one_out_peer_mean(
            df, "style_bucket", value_col, f"style_peer_mean_{value_col}"
        )
        df[f"style_peer_excess_{value_col}"] = df[value_col] - df[
            f"style_peer_mean_{value_col}"
        ]
    style_daily = (
        df.groupby(["date", "style_bucket"], sort=False)
        .agg(
            style_ret_1d=("ret_1d", "mean"),
            style_breadth_1d=("ret_1d", lambda x: float((x > 0).mean())),
            style_n_stocks=("symbol", "count"),
        )
        .reset_index()
        .sort_values(["style_bucket", "date"])
    )
    style_daily["style_ret_20d"] = np.expm1(
        np.log1p(style_daily["style_ret_1d"].clip(lower=-0.999))
        .groupby(style_daily["style_bucket"], sort=False)
        .rolling(20, min_periods=10)
        .sum()
        .reset_index(level=0, drop=True)
    )
    df_tmp = df.merge(style_daily, on=["date", "style_bucket"], how="left", sort=False)
    for col in style_daily.columns:
        if col not in ["date", "style_bucket"]:
            df[col] = df_tmp[col].values

    manifest.add_many(
        [
            f"{prefix}_{kind}_{value_col}"
            for value_col in peer_cols
            for prefix in ["sector_peer", "subind_peer"]
            for kind in ["mean", "excess"]
        ]
        + [
            "hq_state_ret_1d",
            "hq_state_breadth_1d",
            "hq_state_n_stocks",
            "hq_state_ret_20d",
            "hq_region_ret_1d",
            "hq_region_breadth_1d",
            "hq_region_n_stocks",
            "hq_region_ret_20d",
            "style_mom_bucket",
            "style_vol_bucket",
            "style_liq_bucket",
            "style_bucket",
        ]
        + [
            f"style_peer_{kind}_{value_col}"
            for value_col in ["ret_1d", "ret_5d", "ret_20d", "vol_20d", "rsi_14d"]
            for kind in ["mean", "excess"]
        ]
        + ["style_ret_1d", "style_breadth_1d", "style_n_stocks", "style_ret_20d"],
        "peer_style_geography",
        "{feature}: same-sector/subindustry, style-bucket, or headquarters-location peer feature.",
    )


def add_cross_sectional_features(df: pd.DataFrame, manifest: FeatureManifest) -> None:
    base_cols = [
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
    ]
    base_cols = [c for c in base_cols if c in df.columns]
    for col in base_cols:
        date_g = df.groupby("date", sort=False)[col]
        mean = date_g.transform("mean")
        std = date_g.transform("std")
        df[f"cs_z_{col}"] = (df[col] - mean) / std.replace(0, np.nan)
        df[f"cs_rank_{col}"] = date_g.rank(pct=True)

        sec_g = df.groupby(["date", "sector"], sort=False)[col]
        sec_mean = sec_g.transform("mean")
        sec_std = sec_g.transform("std")
        df[f"sector_z_{col}"] = (df[col] - sec_mean) / sec_std.replace(0, np.nan)
        df[f"sector_rank_{col}"] = sec_g.rank(pct=True)

        sub_g = df.groupby(["date", "sub_industry"], sort=False)[col]
        sub_mean = sub_g.transform("mean")
        sub_std = sub_g.transform("std")
        df[f"subind_z_{col}"] = (df[col] - sub_mean) / sub_std.replace(0, np.nan)
        df[f"subind_rank_{col}"] = sub_g.rank(pct=True)

    manifest.add_many(
        [
            f"{scope}_{kind}_{col}"
            for col in base_cols
            for scope in ["cs", "sector", "subind"]
            for kind in ["z", "rank"]
        ],
        "cross_sectional",
        "{feature}: date-wise cross-sectional, sector-neutral, or subindustry-neutral transformation.",
    )


def add_targets(df: pd.DataFrame, price_col: str, manifest: FeatureManifest) -> None:
    g = df.groupby("symbol", sort=False)
    for h in TARGET_WINDOWS:
        future_price = g[price_col].shift(-h)
        df[f"target_ret_fwd_{h}d"] = future_price / df[price_col] - 1
        date_mean = df.groupby("date", sort=False)[f"target_ret_fwd_{h}d"].transform(
            "mean"
        )
        df[f"target_excess_market_fwd_{h}d"] = df[f"target_ret_fwd_{h}d"] - date_mean
        df[f"target_rank_fwd_{h}d"] = df.groupby("date", sort=False)[
            f"target_ret_fwd_{h}d"
        ].rank(pct=True)
        sec_mean = df.groupby(["date", "sector"], sort=False)[
            f"target_ret_fwd_{h}d"
        ].transform("mean")
        df[f"target_excess_sector_fwd_{h}d"] = df[f"target_ret_fwd_{h}d"] - sec_mean

    manifest.add_many(
        [f"target_ret_fwd_{h}d" for h in TARGET_WINDOWS]
        + [f"target_excess_market_fwd_{h}d" for h in TARGET_WINDOWS]
        + [f"target_rank_fwd_{h}d" for h in TARGET_WINDOWS]
        + [f"target_excess_sector_fwd_{h}d" for h in TARGET_WINDOWS],
        "target",
        "{feature}: forward-return target; exclude from model features.",
    )


def optimize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.select_dtypes(include=["float64"]).columns:
        df[col] = df[col].astype("float32")
    for col in df.select_dtypes(include=["int64"]).columns:
        if col not in ["year"]:
            df[col] = pd.to_numeric(df[col], downcast="integer")
    for col in ["symbol", "sector", "sub_industry", "hq_city", "hq_state", "hq_region"]:
        if col in df.columns:
            df[col] = df[col].astype("category")
    return df


def write_outputs(
    df: pd.DataFrame,
    manifest: FeatureManifest,
    args: argparse.Namespace,
    price_col: str,
) -> None:
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = Path(args.metadata)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    manifest_df = manifest.to_frame()
    manifest_df.to_csv(manifest_path, index=False)

    if not args.no_output:
        if out_path.suffix == ".parquet":
            df.to_parquet(out_path, index=False, compression="zstd")
        elif out_path.suffix in {".pkl", ".pickle"}:
            df.to_pickle(out_path)
        elif out_path.suffix == ".csv":
            df.to_csv(out_path, index=False)
        else:
            raise ValueError(
                f"Unsupported output suffix {out_path.suffix!r}; use .parquet, .pkl, or .csv"
            )

    sample_cols = (
        ["date", "symbol", "sector", "sub_industry"]
        + [
            c
            for c in [
                "ret_1d",
                "ret_20d",
                "vol_20d",
                "rsi_14d",
                "volume_z_20d",
                "sector_ret_20d",
                "excess_sector_ret_20d",
                "cs_rank_ret_20d",
                "sector_rank_ret_20d",
                "style_bucket",
                "target_excess_market_fwd_5d",
            ]
            if c in df.columns
        ]
    )
    df.loc[:, sample_cols].head(args.sample_rows).to_csv(args.sample_csv, index=False)

    target_cols = [c for c in df.columns if c.startswith("target_")]
    id_cols = {
        "date",
        "symbol",
        "company",
        "sector",
        "sub_industry",
        "date_added",
        "hq_city",
        "hq_state",
        "hq_region",
    }
    feature_cols = [
        c
        for c in df.columns
        if c not in id_cols and c not in target_cols and not c.startswith("_")
    ]

    metadata = {
        "rows": int(len(df)),
        "symbols": int(df["symbol"].nunique()),
        "date_min": str(df["date"].min().date()),
        "date_max": str(df["date"].max().date()),
        "price_column_used": price_col,
        "total_columns": int(df.shape[1]),
        "feature_columns": int(len(feature_cols)),
        "target_columns": int(len(target_cols)),
        "manifest_rows": int(len(manifest_df)),
        "output_file": None if args.no_output else str(out_path),
        "output_format": out_path.suffix.lstrip(".") if not args.no_output else None,
        "manifest": str(manifest_path),
        "sample_csv": str(args.sample_csv),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def build_features(args: argparse.Namespace) -> tuple[pd.DataFrame, FeatureManifest, str]:
    manifest = FeatureManifest(rows=[])
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

    add_calendar_and_metadata_features(df, manifest)
    add_price_return_features(df, price_col, manifest)
    add_volatility_features(df, manifest)
    add_trend_features(df, price_col, manifest)
    add_liquidity_features(df, manifest)

    # Cross-sectional group features require date order for rolling group states.
    df = df.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)
    add_market_industry_features(df, manifest)
    df = df.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)
    add_beta_and_correlation_features(df, manifest)

    # Peer features use beta/statistical features, so they run after beta.
    df = df.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)
    add_peer_and_style_features(df, manifest)
    add_cross_sectional_features(df, manifest)
    df = df.sort_values(["symbol", "date"], kind="mergesort").reset_index(drop=True)
    add_targets(df, price_col, manifest)
    df = optimize_dtypes(df)
    return df, manifest, price_col


def main() -> None:
    args = parse_args()
    df, manifest, price_col = build_features(args)
    write_outputs(df, manifest, args, price_col)
    print(
        json.dumps(
            {
                "rows": int(len(df)),
                "symbols": int(df["symbol"].nunique()),
                "columns": int(df.shape[1]),
                "features_in_manifest": int(
                    (manifest.to_frame()["category"] != "target").sum()
                ),
                "targets_in_manifest": int(
                    (manifest.to_frame()["category"] == "target").sum()
                ),
                "price_column_used": price_col,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
