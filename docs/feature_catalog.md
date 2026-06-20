# No-External-Data Feature Catalog

This feature set uses only:

- `sp500_stocks.csv`: daily OHLCV and ticker.
- `sp500_companies.csv`: sector, sub-industry, headquarters, `date_added`, and `founded`.

No fundamentals, market cap, supply-chain, analyst, macro, or outside listing-date data is used.

## Price Adjustment

The raw `sp500_stocks.csv` exposes only a `close` column (no separate
`Adj Close`). That `close` series is already **split-adjusted**: NVDA around its
2024-06-10 10:1 split (120.68 -> 121.58) and AAPL around its 2020-08-31 4:1 split
(121.06 -> 125.17) show no split-day gap, which is consistent with a yfinance
`auto_adjust=True` export (split- and dividend-adjusted). All returns, momentum,
volatility, and forward-return targets are therefore computed on an adjusted
price, so stock splits do not inject artificial jumps. Residual uncertainty about
dividend adjustment is treated as a minor data-quality limitation in the report.

## Data Preparation

Run the CSV-to-Parquet preparation step once:

```bash
python scripts/prepare_data.py
```

This writes typed Parquet files under `data/interim/`. Numeric OHLCV columns are stored as `float32`, while `symbol`, `sector`, `sub_industry`, and headquarters fields are stored as categorical columns.

For the full feature build, use the grouped-output script:

```bash
python scripts/make_feature_groups.py
```

This writes feature groups under `data/processed/features_by_group/`. The files share `date` and `symbol` as join keys. They also keep `sector`, `sub_industry`, `hq_state`, and `hq_region` as convenient categorical context columns.

Current full build:

| File | Feature/Target Columns |
|---|---:|
| `calendar_metadata.parquet` | 23 |
| `price_momentum.parquet` | 50 |
| `volatility.parquet` | 69 |
| `trend_technical.parquet` | 56 |
| `liquidity_volume.parquet` | 41 |
| `market_industry.parquet` | 52 |
| `statistical_linkage.parquet` | 8 |
| `peer_style_geography.parquet` | 58 |
| `cross_sectional.parquet` | 168 |
| `targets.parquet` | 48 |

The grouped layout is intentional: a single 500+ column pandas DataFrame is much slower and more memory-intensive than writing feature groups independently. Model training can read only the needed groups and join on `date, symbol`.

## Modeling Unit

Each row is one stock-date observation. Features are built from information available at or before that date. Targets are forward returns and must be excluded from model inputs.

## Feature Groups

### Price, Return, Momentum, And Reversal

Signals include daily/intraday/overnight returns, high-low range, close location in the daily bar, rolling returns over 1/2/3/5/10/20/40/60/120/252 trading days, log returns, reversal versions, skip-window momentum, and momentum acceleration.

Economic intuition: captures short-term reversal, medium-term momentum, and trend acceleration.

### Volatility, Tail, And Drawdown

Signals include rolling return volatility, upside/downside volatility, Parkinson volatility, Garman-Klass volatility, ATR, rolling skew/kurtosis, max/min return, volatility ratios, and drawdown from recent highs.

Economic intuition: controls for risk state, crowding, crash sensitivity, and high-volatility underperformance.

### Trend And Technical Indicators

Signals include SMA/EMA levels and gaps, SMA slopes, MACD line/signal/histogram, RSI, Bollinger z-score/bandwidth/percent-b, rolling channel position, breakout distances, Williams %R, and approximate CCI.

Economic intuition: summarizes trend-following and overbought/oversold states used by technical and systematic traders.

### Liquidity And Volume

Signals include log volume, dollar volume, rolling volume means, volume z-scores, volume ratios, dollar-volume z-scores, volume momentum, volume volatility, Amihud-style illiquidity, and return per log dollar volume.

Economic intuition: captures attention, liquidity shocks, transaction-cost pressure, and price impact.

### Market Regime

Signals include equal-weight market return, market volatility, market breadth, cross-sectional return dispersion, market dollar volume, and market volume z-score.

Economic intuition: relative stock prediction is regime-dependent; the same stock signal can behave differently in high-volatility, low-breadth, or high-dispersion markets.

### Sector And Sub-Industry

Signals include sector/sub-industry daily return, rolling return, volatility, breadth, dispersion, member count, stock excess return versus sector/sub-industry, and sector/sub-industry momentum rank.

Economic intuition: controls for sector rotation and separates stock-specific alpha from group movement.

### Peer, Style, And Geography

Signals include leave-one-out peer means and peer excess values within sector/sub-industry, headquarters-state and headquarters-region peer returns, and coarse style buckets from momentum, volatility, and liquidity terciles.

Economic intuition: approximates same-industry spillover, local economic exposure, and style crowding without external Barra or supply-chain data.

### Cross-Sectional And Neutralized Transforms

Selected raw signals are transformed into date-wise z-scores/ranks, sector-neutral z-scores/ranks, and sub-industry-neutral z-scores/ranks.

Economic intuition: the project asks for relative stock performance, so cross-sectional normalization is usually more useful than raw level prediction.

### Metadata

Signals include firm age from `founded`, legacy firm age when multiple founding years appear, first available trading age, S&P 500 membership age, sector/sub-industry codes, headquarters city/state/region codes, and group sizes.

Important caveat: `date_added` is the S&P 500 inclusion date, not IPO date. `sp500_membership_age_years` is set only after the stock has joined the index. Using current S&P 500 constituents for historical data still has survivorship bias, which should be discussed in the report.

## Targets

The script creates:

- `target_ret_fwd_{h}d`
- `target_excess_market_fwd_{h}d`
- `target_excess_sector_fwd_{h}d`
- `target_rank_fwd_{h}d`

where `h` is one of `1, 5, 20, 30, 40, 50, 60, 70, 80, 90, 120, 150`.

For this case study, the cleanest target is usually an excess-market or rank target, because it aligns with relative return prediction and avoids asking the model to forecast raw market direction. The long-horizon experiments additionally evaluate 30D/40D/50D/60D, 70D/80D/90D, 120D, and 150D targets.

## Recommended Usage

1. Build all features.
2. Drop target columns from `X`.
3. Use chronological train/validation/test splits.
4. Prefer cross-sectional IC, rank IC, top-minus-bottom decile return, turnover, and cost-adjusted long-short performance over raw RMSE alone.
5. Use feature importance and ablation to reduce the candidate set before writing the final report.
