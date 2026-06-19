#!/usr/bin/env python3
"""Train and backtest a cross-sectional S&P 500 alpha model.

This script assumes feature groups have already been built by
``scripts/make_feature_groups.py``. It joins a selected feature set with the
target panel, trains a baseline and a model, then evaluates rank IC, decile
spread, and a long-short decile portfolio.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


KEY_COLS = ["date", "symbol"]
META_COLS = ["sector", "sub_industry", "hq_state", "hq_region"]
TARGET_PREFIX = "target_"

CORE_FEATURES = [
    # Price momentum and short-term reversal
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
    # Volatility and drawdown
    "vol_20d",
    "vol_60d",
    "downside_vol_20d",
    "parkinson_vol_20d",
    "gk_vol_20d",
    "vol_ratio_20_60",
    "drawdown_from_60d_high",
    "drawdown_from_252d_high",
    # Technical indicators
    "rsi_14d",
    "sma_gap_20d",
    "sma_gap_50d",
    "sma_gap_200d",
    "macd_line",
    "macd_signal",
    "macd_hist",
    "boll_z_20d",
    "boll_bandwidth_20d",
    "channel_pos_20d",
    # Liquidity and volume
    "log_dollar_volume",
    "volume_z_20d",
    "dollar_volume_z_20d",
    "volume_mom_20d",
    "amihud_20d",
    "ret_per_log_dollar_volume",
    # Market, industry, peer, and beta context
    "market_ret_1d",
    "market_ret_20d",
    "market_vol_20d",
    "market_breadth_20d",
    "excess_sector_ret_20d",
    "excess_subind_ret_20d",
    "sector_mom_rank_20d",
    "subind_mom_rank_20d",
    "beta_60d",
    "corr_market_60d",
    "idio_vol_60d",
    "sector_peer_excess_ret_20d",
    "subind_peer_excess_ret_20d",
    # Cross-sectional normalized versions of key raw signals
    "cs_rank_ret_20d",
    "cs_rank_ret_60d",
    "cs_rank_mom_252d_skip_21d",
    "cs_rank_vol_20d",
    "cs_rank_volume_z_20d",
    "cs_rank_rsi_14d",
    "cs_rank_sma_gap_20d",
    "cs_rank_boll_z_20d",
    "cs_rank_beta_60d",
    "cs_rank_excess_sector_ret_20d",
    "sector_rank_mom_252d_skip_21d",
    "sector_rank_sma_gap_20d",
    "sector_rank_beta_60d",
]


@dataclass
class Preprocessor:
    feature_cols: list[str]
    medians: np.ndarray
    means: np.ndarray
    stds: np.ndarray

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        x = df.loc[:, self.feature_cols].to_numpy(dtype=np.float32, copy=True)
        x[~np.isfinite(x)] = np.nan
        if np.isnan(x).any():
            inds = np.where(np.isnan(x))
            x[inds] = np.take(self.medians, inds[1]).astype(np.float32)
        x = (x - self.means.astype(np.float32)) / self.stds.astype(np.float32)
        x[~np.isfinite(x)] = 0.0
        return x


class NumpyRidgeRegressor:
    """Small ridge regressor so the baseline runs without scikit-learn."""

    def __init__(self, alpha: float = 10.0) -> None:
        self.alpha = alpha
        self.intercept_: float = 0.0
        self.coef_: np.ndarray | None = None

    def fit(self, x: np.ndarray, y: np.ndarray) -> "NumpyRidgeRegressor":
        x64 = x.astype(np.float64, copy=False)
        y64 = y.astype(np.float64, copy=False)
        self.intercept_ = float(np.nanmean(y64))
        yc = y64 - self.intercept_
        xtx = x64.T @ x64
        xtx.flat[:: xtx.shape[0] + 1] += self.alpha
        xty = x64.T @ yc
        self.coef_ = np.linalg.solve(xtx, xty)
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        if self.coef_ is None:
            raise RuntimeError("Model is not fitted.")
        return (x.astype(np.float64, copy=False) @ self.coef_ + self.intercept_).astype(
            np.float32
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-dir", default="data/processed/features_by_group")
    parser.add_argument(
        "--feature-map", default="data/processed/feature_columns_by_group.csv"
    )
    parser.add_argument("--out-dir", default="output/model_pipeline")
    parser.add_argument("--run-name", default=None)
    parser.add_argument("--target-col", default="target_excess_sector_fwd_5d")
    parser.add_argument("--return-col", default="target_ret_fwd_5d")
    parser.add_argument("--train-end", default="2018-12-31")
    parser.add_argument("--val-end", default="2020-12-31")
    parser.add_argument("--start-date", default="2005-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument(
        "--feature-set",
        choices=["core", "all"],
        default="core",
        help="core is the default runnable research set; all joins every non-target feature.",
    )
    parser.add_argument(
        "--feature-groups",
        nargs="*",
        default=None,
        help="Optional group filenames or stems to include instead of feature-set core/all.",
    )
    parser.add_argument(
        "--model",
        choices=["ridge", "sklearn-hgb", "xgboost", "lightgbm", "auto"],
        default="ridge",
    )
    parser.add_argument("--ridge-alpha", type=float, default=25.0)
    parser.add_argument("--max-train-rows", type=int, default=None)
    parser.add_argument("--max-eval-rows", type=int, default=None)
    parser.add_argument("--sample-seed", type=int, default=42)
    parser.add_argument("--rebalance-every", type=int, default=5)
    parser.add_argument("--long-short-pct", type=float, default=0.10)
    parser.add_argument("--min-names-per-date", type=int, default=100)
    parser.add_argument("--transaction-cost-bps", type=float, default=5.0)
    parser.add_argument("--sector-neutral", action="store_true")
    parser.add_argument("--save-predictions", action="store_true")
    parser.add_argument("--n-estimators", type=int, default=300)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--num-leaves", type=int, default=63)
    parser.add_argument("--min-child-samples", type=int, default=100)
    parser.add_argument("--min-child-weight", type=float, default=20.0)
    parser.add_argument("--subsample", type=float, default=0.8)
    parser.add_argument("--colsample-bytree", type=float, default=0.8)
    parser.add_argument("--reg-alpha", type=float, default=0.0)
    parser.add_argument("--reg-lambda", type=float, default=5.0)
    parser.add_argument("--n-jobs", type=int, default=-1)
    return parser.parse_args()


def now_run_name() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def normalize_group_name(name: str) -> str:
    return name if name.endswith(".parquet") else f"{name}.parquet"


def read_feature_map(path: str | Path) -> pd.DataFrame:
    fmap = pd.read_csv(path)
    if not {"file", "column"}.issubset(fmap.columns):
        raise ValueError("feature map must contain file and column columns")
    return fmap


def select_feature_columns(args: argparse.Namespace, fmap: pd.DataFrame) -> list[str]:
    valid = set(fmap["column"])
    if args.feature_groups:
        groups = {normalize_group_name(g) for g in args.feature_groups}
        cols = fmap.loc[fmap["file"].isin(groups), "column"].tolist()
    elif args.feature_set == "all":
        cols = fmap["column"].tolist()
    else:
        cols = [c for c in CORE_FEATURES if c in valid]

    missing = [c for c in CORE_FEATURES if c not in valid]
    if args.feature_set == "core" and missing:
        print(f"Warning: {len(missing)} core features not found and skipped: {missing}")

    cols = [c for c in dict.fromkeys(cols) if c in valid and not c.startswith(TARGET_PREFIX)]
    if not cols:
        raise ValueError("No usable feature columns selected.")
    return cols


def load_panel(args: argparse.Namespace, feature_cols: list[str], fmap: pd.DataFrame) -> pd.DataFrame:
    feature_dir = Path(args.feature_dir)
    target_path = feature_dir / "targets.parquet"
    target_cols = [args.target_col, args.return_col]
    target_read_cols = KEY_COLS + META_COLS + list(dict.fromkeys(target_cols))
    print(f"Loading targets: {target_path}")
    panel = pd.read_parquet(target_path, columns=target_read_cols)

    if args.start_date:
        panel = panel.loc[panel["date"] >= pd.Timestamp(args.start_date)]
    if args.end_date:
        panel = panel.loc[panel["date"] <= pd.Timestamp(args.end_date)]

    by_file = (
        fmap.loc[fmap["column"].isin(feature_cols)]
        .groupby("file")["column"]
        .apply(list)
        .to_dict()
    )
    for file_name, cols in sorted(by_file.items()):
        path = feature_dir / file_name
        read_cols = KEY_COLS + cols
        print(f"Joining {file_name}: {len(cols)} features")
        part = pd.read_parquet(path, columns=read_cols)
        if args.start_date:
            part = part.loc[part["date"] >= pd.Timestamp(args.start_date)]
        if args.end_date:
            part = part.loc[part["date"] <= pd.Timestamp(args.end_date)]
        panel = panel.merge(part, on=KEY_COLS, how="left", sort=False)
        del part

    panel = panel.dropna(subset=[args.target_col, args.return_col]).copy()
    panel = panel.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)
    return panel


def split_masks(df: pd.DataFrame, train_end: str, val_end: str) -> dict[str, np.ndarray]:
    train_end_ts = pd.Timestamp(train_end)
    val_end_ts = pd.Timestamp(val_end)
    dates = df["date"]
    return {
        "train": (dates <= train_end_ts).to_numpy(),
        "val": ((dates > train_end_ts) & (dates <= val_end_ts)).to_numpy(),
        "test": (dates > val_end_ts).to_numpy(),
    }


def sample_mask(mask: np.ndarray, max_rows: int | None, seed: int) -> np.ndarray:
    idx = np.flatnonzero(mask)
    if max_rows is None or len(idx) <= max_rows:
        return mask
    rng = np.random.default_rng(seed)
    keep = rng.choice(idx, size=max_rows, replace=False)
    out = np.zeros_like(mask, dtype=bool)
    out[keep] = True
    return out


def limit_eval_mask_by_date(df: pd.DataFrame, mask: np.ndarray, max_rows: int | None) -> np.ndarray:
    """Limit evaluation rows while keeping complete daily cross-sections."""
    if max_rows is None or int(mask.sum()) <= max_rows:
        return mask
    counts = df.loc[mask].groupby("date", sort=True).size()
    keep_dates = counts.loc[counts.cumsum() <= max_rows].index
    if len(keep_dates) == 0:
        keep_dates = counts.index[:1]
    return (mask & df["date"].isin(keep_dates).to_numpy())


def fit_preprocessor(df: pd.DataFrame, feature_cols: list[str], train_mask: np.ndarray) -> Preprocessor:
    x = df.loc[train_mask, feature_cols].to_numpy(dtype=np.float32, copy=True)
    x[~np.isfinite(x)] = np.nan
    medians = np.nanmedian(x, axis=0)
    medians[~np.isfinite(medians)] = 0.0
    if np.isnan(x).any():
        inds = np.where(np.isnan(x))
        x[inds] = np.take(medians, inds[1]).astype(np.float32)
    means = np.nanmean(x, axis=0)
    stds = np.nanstd(x, axis=0)
    means[~np.isfinite(means)] = 0.0
    stds[(~np.isfinite(stds)) | (stds == 0)] = 1.0
    return Preprocessor(feature_cols, medians, means, stds)


def fit_model(args: argparse.Namespace, x_train: np.ndarray, y_train: np.ndarray):
    model_name = args.model
    if model_name == "auto":
        if importlib.util.find_spec("lightgbm"):
            model_name = "lightgbm"
        elif importlib.util.find_spec("xgboost"):
            model_name = "xgboost"
        elif importlib.util.find_spec("sklearn"):
            model_name = "sklearn-hgb"
        else:
            model_name = "ridge"

    if model_name == "lightgbm":
        from lightgbm import LGBMRegressor

        model = LGBMRegressor(
            n_estimators=args.n_estimators,
            learning_rate=args.learning_rate,
            num_leaves=args.num_leaves,
            max_depth=args.max_depth,
            min_child_samples=args.min_child_samples,
            subsample=args.subsample,
            colsample_bytree=args.colsample_bytree,
            reg_alpha=args.reg_alpha,
            reg_lambda=args.reg_lambda,
            random_state=args.sample_seed,
            n_jobs=args.n_jobs,
            verbose=-1,
        )
    elif model_name == "xgboost":
        from xgboost import XGBRegressor

        model = XGBRegressor(
            n_estimators=args.n_estimators,
            max_depth=args.max_depth,
            learning_rate=args.learning_rate,
            min_child_weight=args.min_child_weight,
            subsample=args.subsample,
            colsample_bytree=args.colsample_bytree,
            reg_alpha=args.reg_alpha,
            reg_lambda=args.reg_lambda,
            objective="reg:squarederror",
            tree_method="hist",
            random_state=args.sample_seed,
            n_jobs=args.n_jobs,
        )
    elif model_name == "sklearn-hgb":
        from sklearn.ensemble import HistGradientBoostingRegressor

        model = HistGradientBoostingRegressor(
            max_iter=args.n_estimators,
            learning_rate=args.learning_rate,
            max_leaf_nodes=31,
            l2_regularization=0.01,
            random_state=args.sample_seed,
        )
    else:
        model = NumpyRidgeRegressor(alpha=args.ridge_alpha)
        model_name = "ridge"

    print(f"Training model: {model_name}")
    model.fit(x_train, y_train)
    return model_name, model


def spearman_by_date(df: pd.DataFrame, score_col: str, target_col: str, min_names: int) -> pd.DataFrame:
    rows = []
    for dt, g in df.groupby("date", sort=True):
        g = g[[score_col, target_col]].dropna()
        if len(g) < min_names:
            continue
        corr = g[score_col].rank().corr(g[target_col].rank())
        rows.append({"date": dt, "rank_ic": corr, "n": len(g)})
    return pd.DataFrame(rows)


def decile_spread_by_date(
    df: pd.DataFrame,
    score_col: str,
    target_col: str,
    pct: float,
    min_names: int,
) -> pd.DataFrame:
    rows = []
    for dt, g in df.groupby("date", sort=True):
        g = g[[score_col, target_col]].dropna().sort_values(score_col)
        if len(g) < min_names:
            continue
        k = max(1, int(len(g) * pct))
        bottom = g.head(k)[target_col].mean()
        top = g.tail(k)[target_col].mean()
        rows.append(
            {
                "date": dt,
                "top_mean": top,
                "bottom_mean": bottom,
                "top_bottom_spread": top - bottom,
                "n": len(g),
                "bucket_size": k,
            }
        )
    return pd.DataFrame(rows)


def choose_weights(
    g: pd.DataFrame,
    score_col: str,
    pct: float,
    min_names: int,
    sector_neutral: bool,
) -> pd.Series:
    if not sector_neutral:
        h = g[["symbol", score_col]].dropna().sort_values(score_col)
        if len(h) < min_names:
            return pd.Series(dtype=np.float64)
        k = max(1, int(len(h) * pct))
        longs = h.tail(k)["symbol"].astype(str)
        shorts = h.head(k)["symbol"].astype(str)
        weights = pd.Series(0.5 / len(longs), index=longs)
        weights = pd.concat([weights, pd.Series(-0.5 / len(shorts), index=shorts)])
        return weights.groupby(level=0).sum()

    sector_weights = []
    usable = 0
    for _, sg in g.groupby("sector", sort=False):
        h = sg[["symbol", score_col]].dropna().sort_values(score_col)
        if len(h) < max(10, int(min_names * pct)):
            continue
        k = max(1, int(len(h) * pct))
        if len(h) < 2 * k:
            continue
        longs = h.tail(k)["symbol"].astype(str)
        shorts = h.head(k)["symbol"].astype(str)
        sector_weights.append((longs, shorts))
        usable += 1
    if usable == 0:
        return pd.Series(dtype=np.float64)
    chunks = []
    for longs, shorts in sector_weights:
        chunks.append(pd.Series(0.5 / usable / len(longs), index=longs))
        chunks.append(pd.Series(-0.5 / usable / len(shorts), index=shorts))
    return pd.concat(chunks).groupby(level=0).sum()


def run_backtest(
    df: pd.DataFrame,
    score_col: str,
    return_col: str,
    pct: float,
    rebalance_every: int,
    cost_bps: float,
    min_names: int,
    sector_neutral: bool,
) -> pd.DataFrame:
    unique_dates = pd.Index(sorted(df["date"].unique()))
    rebalance_dates = unique_dates[::rebalance_every]
    prev_w = pd.Series(dtype=np.float64)
    rows = []
    for dt in rebalance_dates:
        g = df.loc[df["date"] == dt, ["symbol", "sector", score_col, return_col]].dropna()
        if len(g) < min_names:
            continue
        weights = choose_weights(g, score_col, pct, min_names, sector_neutral)
        if weights.empty:
            continue
        returns = g.set_index("symbol")[return_col]
        gross_ret = float((weights * returns.reindex(weights.index)).sum())
        all_idx = weights.index.union(prev_w.index)
        turnover = 0.5 * float(
            (weights.reindex(all_idx, fill_value=0.0) - prev_w.reindex(all_idx, fill_value=0.0))
            .abs()
            .sum()
        )
        cost = turnover * cost_bps / 10000.0
        rows.append(
            {
                "date": dt,
                "gross_return": gross_ret,
                "turnover": turnover,
                "cost": cost,
                "net_return": gross_ret - cost,
                "n_positions": int((weights != 0).sum()),
                "gross_exposure": float(weights.abs().sum()),
                "net_exposure": float(weights.sum()),
            }
        )
        prev_w = weights
    out = pd.DataFrame(rows)
    if not out.empty:
        out["equity_gross"] = (1.0 + out["gross_return"]).cumprod()
        out["equity_net"] = (1.0 + out["net_return"]).cumprod()
    return out


def summarize_ic(ic: pd.DataFrame, periods_per_year: float = 252.0) -> dict[str, float]:
    if ic.empty:
        return {"mean_rank_ic": math.nan, "rank_ic_std": math.nan, "rank_ic_ir": math.nan}
    vals = ic["rank_ic"].dropna()
    return {
        "mean_rank_ic": float(vals.mean()),
        "rank_ic_std": float(vals.std(ddof=1)),
        "rank_ic_ir": float(vals.mean() / (vals.std(ddof=1) + 1e-12) * math.sqrt(periods_per_year)),
        "ic_dates": int(len(vals)),
    }


def summarize_spread(spread: pd.DataFrame, periods_per_year: float) -> dict[str, float]:
    if spread.empty:
        return {"mean_top_bottom_spread": math.nan, "spread_ir": math.nan}
    vals = spread["top_bottom_spread"].dropna()
    return {
        "mean_top_bottom_spread": float(vals.mean()),
        "spread_std": float(vals.std(ddof=1)),
        "spread_ir": float(vals.mean() / (vals.std(ddof=1) + 1e-12) * math.sqrt(periods_per_year)),
        "spread_dates": int(len(vals)),
    }


def summarize_backtest(bt: pd.DataFrame, periods_per_year: float) -> dict[str, float]:
    if bt.empty:
        return {
            "ann_return_net": math.nan,
            "ann_vol_net": math.nan,
            "sharpe_net": math.nan,
            "max_drawdown_net": math.nan,
        }
    r = bt["net_return"].dropna()
    equity = (1.0 + r).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    ann_ret = float(r.mean() * periods_per_year)
    ann_vol = float(r.std(ddof=1) * math.sqrt(periods_per_year))
    return {
        "periods": int(len(r)),
        "mean_period_return_net": float(r.mean()),
        "ann_return_net": ann_ret,
        "ann_vol_net": ann_vol,
        "sharpe_net": float(ann_ret / (ann_vol + 1e-12)),
        "max_drawdown_net": float(drawdown.min()),
        "avg_turnover": float(bt["turnover"].mean()),
        "avg_cost": float(bt["cost"].mean()),
        "final_equity_net": float(equity.iloc[-1]),
    }


def evaluate_scores(
    df: pd.DataFrame,
    score_col: str,
    target_col: str,
    return_col: str,
    args: argparse.Namespace,
    split_name: str,
    out_dir: Path,
) -> dict[str, object]:
    periods_per_year = 252.0 / args.rebalance_every
    ic = spearman_by_date(df, score_col, target_col, args.min_names_per_date)
    spread = decile_spread_by_date(
        df, score_col, target_col, args.long_short_pct, args.min_names_per_date
    )
    bt = run_backtest(
        df,
        score_col,
        return_col,
        args.long_short_pct,
        args.rebalance_every,
        args.transaction_cost_bps,
        args.min_names_per_date,
        args.sector_neutral,
    )
    ic.to_csv(out_dir / f"{score_col}_{split_name}_rank_ic.csv", index=False)
    spread.to_csv(out_dir / f"{score_col}_{split_name}_decile_spread.csv", index=False)
    bt.to_csv(out_dir / f"{score_col}_{split_name}_backtest.csv", index=False)
    metrics = {
        **summarize_ic(ic),
        **summarize_spread(spread, periods_per_year),
        **summarize_backtest(bt, periods_per_year),
        "rows": int(len(df)),
        "dates": int(df["date"].nunique()),
    }
    return metrics


def write_summary_markdown(
    out_path: Path,
    args: argparse.Namespace,
    model_name: str,
    feature_cols: list[str],
    metrics: dict[str, dict[str, object]],
) -> None:
    lines = [
        "# Model Pipeline Summary",
        "",
        f"- Target: `{args.target_col}`",
        f"- Portfolio return column: `{args.return_col}`",
        f"- Model: `{model_name}`",
        f"- Feature count: {len(feature_cols)}",
        f"- Train end: {args.train_end}",
        f"- Validation end: {args.val_end}",
        f"- Rebalance every: {args.rebalance_every} trading days",
        f"- Transaction cost: {args.transaction_cost_bps:.2f} bps per one-way turnover",
        f"- Sector neutral portfolio: {args.sector_neutral}",
        "",
        "## Metrics",
        "",
        "| score | split | mean IC | ICIR | spread | ann net return | ann vol | Sharpe | max DD | turnover |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for score, by_split in metrics.items():
        for split, m in by_split.items():
            lines.append(
                "| {score} | {split} | {ic:.4f} | {icir:.2f} | {spread:.4f} | {ann:.2%} | {vol:.2%} | {sharpe:.2f} | {dd:.2%} | {turn:.2%} |".format(
                    score=score,
                    split=split,
                    ic=m.get("mean_rank_ic", math.nan),
                    icir=m.get("rank_ic_ir", math.nan),
                    spread=m.get("mean_top_bottom_spread", math.nan),
                    ann=m.get("ann_return_net", math.nan),
                    vol=m.get("ann_vol_net", math.nan),
                    sharpe=m.get("sharpe_net", math.nan),
                    dd=m.get("max_drawdown_net", math.nan),
                    turn=m.get("avg_turnover", math.nan),
                )
            )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Baseline score is a single cross-sectional momentum rank feature.",
            "- Model score is trained only on rows up to the configured train split.",
            "- The default target is sector-relative future return; the backtest uses raw forward return for realized PnL.",
            "- This uses the current S&P 500 constituent dataset, so survivorship bias remains a report limitation.",
        ]
    )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    run_name = args.run_name or now_run_name()
    out_dir = Path(args.out_dir) / run_name
    out_dir.mkdir(parents=True, exist_ok=True)

    fmap = read_feature_map(args.feature_map)
    feature_cols = select_feature_columns(args, fmap)
    panel = load_panel(args, feature_cols, fmap)
    print(
        json.dumps(
            {
                "rows": len(panel),
                "dates": int(panel["date"].nunique()),
                "symbols": int(panel["symbol"].nunique()),
                "date_min": str(panel["date"].min().date()),
                "date_max": str(panel["date"].max().date()),
                "features": len(feature_cols),
            },
            indent=2,
        )
    )

    masks = split_masks(panel, args.train_end, args.val_end)
    train_fit_mask = sample_mask(masks["train"], args.max_train_rows, args.sample_seed)
    prep = fit_preprocessor(panel, feature_cols, train_fit_mask)
    x_train = prep.transform(panel.loc[train_fit_mask])
    y_train = panel.loc[train_fit_mask, args.target_col].to_numpy(dtype=np.float32)

    model_name, model = fit_model(args, x_train, y_train)
    del x_train, y_train

    baseline_feature = (
        "cs_rank_mom_252d_skip_21d"
        if "cs_rank_mom_252d_skip_21d" in panel.columns
        else feature_cols[0]
    )
    panel["baseline_score"] = panel[baseline_feature].astype("float32")

    eval_masks = {
        split: limit_eval_mask_by_date(panel, masks[split], args.max_eval_rows)
        for split in ["val", "test"]
    }

    for split in ["val", "test"]:
        mask = eval_masks[split]
        if not mask.any():
            continue
        x = prep.transform(panel.loc[mask])
        panel.loc[mask, "model_score"] = model.predict(x)
        del x

    metrics: dict[str, dict[str, object]] = {"baseline_score": {}, "model_score": {}}
    for split in ["val", "test"]:
        mask = eval_masks[split]
        if not mask.any():
            continue
        split_df = panel.loc[mask].copy()
        for score_col in ["baseline_score", "model_score"]:
            if score_col not in split_df.columns or split_df[score_col].notna().sum() == 0:
                continue
            metrics[score_col][split] = evaluate_scores(
                split_df,
                score_col,
                args.target_col,
                args.return_col,
                args,
                split,
                out_dir,
            )

    feature_importance = pd.DataFrame({"feature": feature_cols})
    if isinstance(model, NumpyRidgeRegressor):
        feature_importance["importance"] = np.abs(model.coef_)
        feature_importance["coefficient"] = model.coef_
    elif hasattr(model, "feature_importances_"):
        feature_importance["importance"] = getattr(model, "feature_importances_")
    else:
        feature_importance["importance"] = np.nan
    feature_importance.sort_values("importance", ascending=False).to_csv(
        out_dir / "feature_importance.csv", index=False
    )

    if args.save_predictions:
        pred_cols = KEY_COLS + META_COLS + [args.target_col, args.return_col, "baseline_score", "model_score"]
        panel.loc[masks["val"] | masks["test"], pred_cols].to_parquet(
            out_dir / "predictions_val_test.parquet", index=False
        )

    config = vars(args).copy()
    config["run_name"] = run_name
    config["model_resolved"] = model_name
    config["feature_count"] = len(feature_cols)
    (out_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    pd.DataFrame({"feature": feature_cols}).to_csv(out_dir / "selected_features.csv", index=False)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    write_summary_markdown(out_dir / "summary.md", args, model_name, feature_cols, metrics)
    print(f"Done. Results written to {out_dir}")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
