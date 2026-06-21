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
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


KEY_COLS = ["date", "symbol"]
META_COLS = ["sector", "sub_industry", "hq_state", "hq_region"]
TARGET_PREFIX = "target_"
EVAL_TARGET_COL = "_eval_target"
RAW_EVAL_TARGET_COL = "_raw_eval_target"
EVAL_RETURN_COL = "_eval_return"
LABEL_END_DATE_COL = "_label_end_date"
GRAPH_FEATURES = [f"graph_emb_{i}" for i in range(16)] + [
    "graph_rel_weight_sector",
    "graph_rel_weight_style_knn",
    "graph_rel_weight_rolling_corr",
]
REGIME_PERIODS = {
    "gfc_2008": ("2008-01-01", "2009-12-31"),
    "covid_2020": ("2020-01-01", "2020-12-31"),
    "inflation_2022": ("2022-01-01", "2022-12-31"),
}
SUPERVISED_GRAPH_FEATURES = [f"supervised_graph_emb_{i}" for i in range(16)] + [
    "supervised_graph_score",
    "supervised_graph_rel_weight_sector",
    "supervised_graph_rel_weight_style_knn",
    "supervised_graph_rel_weight_rolling_corr",
]

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


class TorchMLPRegressor:
    """Small MLP regressor with early stopping; sklearn-like fit/predict.

    Inputs are assumed already standardized by the pipeline ``Preprocessor``. The
    target is standardized internally for stable optimization and de-standardized
    on predict. A random validation split drives early stopping, which limits
    overfitting on noisy return labels (a known risk for neural nets here).
    """

    def __init__(
        self,
        hidden: tuple[int, ...] = (128, 64),
        dropout: float = 0.1,
        weight_decay: float = 1e-4,
        lr: float = 1e-3,
        epochs: int = 30,
        batch_size: int = 8192,
        patience: int = 5,
        seed: int = 42,
    ) -> None:
        self.hidden = tuple(hidden) or (128, 64)
        self.dropout = float(dropout)
        self.weight_decay = float(weight_decay)
        self.lr = float(lr)
        self.epochs = int(epochs)
        self.batch_size = int(batch_size)
        self.patience = int(patience)
        self.seed = int(seed)
        self._model = None
        self._device = "cpu"
        self._y_mean = 0.0
        self._y_std = 1.0

    def _build(self, n_features: int):
        from torch import nn

        layers: list = []
        prev = n_features
        for h in self.hidden:
            layers += [nn.Linear(prev, h), nn.ReLU(), nn.Dropout(self.dropout)]
            prev = h
        layers.append(nn.Linear(prev, 1))
        return nn.Sequential(*layers)

    def fit(self, x: np.ndarray, y: np.ndarray) -> "TorchMLPRegressor":
        import torch
        from torch import nn

        torch.manual_seed(self.seed)
        rng = np.random.default_rng(self.seed)
        if torch.cuda.is_available():
            self._device = "cuda"
        elif torch.backends.mps.is_available():
            self._device = "mps"
        else:
            self._device = "cpu"
        x = np.ascontiguousarray(x, dtype=np.float32)
        y = np.asarray(y, dtype=np.float32).reshape(-1)
        finite = np.isfinite(y)
        x, y = x[finite], y[finite]
        self._y_mean = float(np.mean(y)) if len(y) else 0.0
        self._y_std = float(np.std(y)) or 1.0
        y_std = (y - self._y_mean) / self._y_std
        n = len(x)
        idx = rng.permutation(n)
        n_val = max(1, int(n * 0.1))
        val_idx, tr_idx = idx[:n_val], idx[n_val:]
        model = self._build(x.shape[1]).to(self._device)
        opt = torch.optim.Adam(model.parameters(), lr=self.lr, weight_decay=self.weight_decay)
        loss_fn = nn.MSELoss()
        xt = torch.from_numpy(x)
        yt = torch.from_numpy(y_std)
        xv = xt[val_idx].to(self._device)
        yv = yt[val_idx].to(self._device)
        best_val = float("inf")
        best_state = None
        bad = 0
        for _ in range(self.epochs):
            model.train()
            order = rng.permutation(len(tr_idx))
            shuffled = tr_idx[order]
            for start in range(0, len(shuffled), self.batch_size):
                b = shuffled[start : start + self.batch_size]
                xb = xt[b].to(self._device)
                yb = yt[b].to(self._device)
                opt.zero_grad()
                pred = model(xb).reshape(-1)
                loss = loss_fn(pred, yb)
                loss.backward()
                opt.step()
            model.eval()
            with torch.no_grad():
                vloss = float(loss_fn(model(xv).reshape(-1), yv).item())
            if vloss < best_val - 1e-6:
                best_val = vloss
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
                bad = 0
            else:
                bad += 1
                if bad >= self.patience:
                    break
        if best_state is not None:
            model.load_state_dict(best_state)
        self._model = model
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        import torch

        if self._model is None:
            raise RuntimeError("Model is not fitted.")
        x = np.ascontiguousarray(x, dtype=np.float32)
        self._model.eval()
        out = np.empty(len(x), dtype=np.float32)
        with torch.no_grad():
            for start in range(0, len(x), self.batch_size):
                xb = torch.from_numpy(x[start : start + self.batch_size]).to(self._device)
                out[start : start + xb.shape[0]] = self._model(xb).reshape(-1).cpu().numpy()
        return out * self._y_std + self._y_mean


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
    parser.add_argument("--include-graph-embeddings", action="store_true")
    parser.add_argument(
        "--graph-embedding-path",
        default="data/processed/graph_embeddings/graph_relation_embeddings_daily.parquet",
    )
    parser.add_argument("--include-supervised-graph-embeddings", action="store_true")
    parser.add_argument(
        "--supervised-graph-embedding-path",
        default=None,
        help="Required with --include-supervised-graph-embeddings; use the target-matched supervised GAT OOF parquet.",
    )
    parser.add_argument(
        "--max-lookback-days",
        type=int,
        default=None,
        help="Optional feature-window filter. Features with day lookbacks larger than this are skipped.",
    )
    parser.add_argument(
        "--model",
        choices=["ridge", "sklearn-hgb", "xgboost", "lightgbm", "mlp", "auto"],
        default="ridge",
    )
    parser.add_argument("--ridge-alpha", type=float, default=25.0)
    parser.add_argument("--mlp-hidden", default="128,64")
    parser.add_argument("--mlp-dropout", type=float, default=0.1)
    parser.add_argument("--mlp-weight-decay", type=float, default=1e-4)
    parser.add_argument("--mlp-lr", type=float, default=1e-3)
    parser.add_argument("--mlp-epochs", type=int, default=30)
    parser.add_argument("--mlp-batch-size", type=int, default=8192)
    parser.add_argument("--mlp-patience", type=int, default=5)
    parser.add_argument("--max-train-rows", type=int, default=None)
    parser.add_argument("--max-eval-rows", type=int, default=None)
    parser.add_argument("--sample-seed", type=int, default=42)
    parser.add_argument(
        "--execution-lag-days",
        type=int,
        default=1,
        help="Trading-day lag between feature date and target/portfolio return start.",
    )
    parser.add_argument(
        "--embargo-days",
        type=int,
        default=None,
        help="Trading days to remove from the start of val/test; default equals target horizon.",
    )
    parser.add_argument(
        "--rebalance-every",
        type=int,
        default=None,
        help="Rebalance interval in trading days; default equals the target horizon so "
        "portfolio returns are non-overlapping.",
    )
    parser.add_argument("--long-short-pct", type=float, default=0.10)
    parser.add_argument("--min-names-per-date", type=int, default=100)
    parser.add_argument("--transaction-cost-bps", type=float, default=5.0)
    parser.add_argument(
        "--winsorize-pct",
        type=float,
        default=0.01,
        help="Per-date cross-sectional winsorization fraction for features; 0 disables.",
    )
    parser.add_argument(
        "--min-dollar-volume-pct",
        type=float,
        default=0.10,
        help="Drop this bottom fraction of names per date by log dollar volume; 0 disables.",
    )
    parser.add_argument("--sector-neutral", action="store_true")
    parser.add_argument(
        "--target-residualize-factors",
        nargs="*",
        default=None,
        help=(
            "Optional feature columns used to residualize the effective training target "
            "within each date. This trains the model on style/factor-neutral residual alpha "
            "while the portfolio backtest still uses --return-col."
        ),
    )
    parser.add_argument(
        "--target-residualize-sector",
        action="store_true",
        help="Include same-date sector dummies in the target residualization design matrix.",
    )
    parser.add_argument(
        "--target-residualize-ridge-alpha",
        type=float,
        default=1.0,
        help="Ridge penalty for per-date target residualization.",
    )
    parser.add_argument(
        "--regime-periods-json",
        default=None,
        help="Optional JSON mapping regime name to [start_date, end_date].",
    )
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
    parser.add_argument(
        "--xgboost-device",
        default="cpu",
        help="XGBoost execution device, for example 'cpu' or 'cuda'.",
    )
    parser.add_argument(
        "--lightgbm-device-type",
        default="cpu",
        choices=["cpu", "gpu", "cuda"],
        help="LightGBM device_type. The pip wheel may not support gpu/cuda on every host.",
    )
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
    if args.max_lookback_days is not None:
        cols = [c for c in cols if feature_within_lookback(c, args.max_lookback_days)]
    if not cols:
        raise ValueError("No usable feature columns selected.")
    return cols


def target_residual_factor_columns(args: argparse.Namespace, fmap: pd.DataFrame) -> list[str]:
    raw = getattr(args, "target_residualize_factors", None)
    if raw is None:
        return []
    valid = set(fmap["column"])
    missing = [c for c in raw if c not in valid]
    if missing:
        raise ValueError(
            "--target-residualize-factors contains columns missing from the feature map: "
            + ", ".join(missing)
        )
    return list(dict.fromkeys(raw))


def feature_within_lookback(col: str, max_days: int) -> bool:
    lookbacks = [int(x) for x in re.findall(r"(?<!\d)(\d+)d(?!\d)", col)]
    skip_match = re.search(r"skip_(\d+)d", col)
    if skip_match:
        lookbacks.append(int(skip_match.group(1)))
    return not lookbacks or max(lookbacks) <= max_days


def infer_horizon_days(*column_names: str) -> int:
    horizons = []
    for name in column_names:
        match = re.search(r"_fwd_(\d+)d$", str(name))
        if not match:
            raise ValueError(f"Cannot infer forward horizon from column name: {name}")
        horizons.append(int(match.group(1)))
    if len(set(horizons)) != 1:
        raise ValueError(f"Target/return horizons must match, got {dict(zip(column_names, horizons))}")
    return horizons[0]


def resolve_embargo_days(horizon_days: int, embargo_days: int | None) -> int:
    if embargo_days is None:
        return horizon_days
    if embargo_days < 0:
        raise ValueError("--embargo-days must be >= 0")
    return embargo_days


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

    graph_cols = [c for c in feature_cols if c in GRAPH_FEATURES]
    if graph_cols:
        graph_path = Path(args.graph_embedding_path)
        print(f"Joining graph embeddings: {graph_path} ({len(graph_cols)} features)")
        graph = pd.read_parquet(graph_path, columns=KEY_COLS + graph_cols)
        if args.start_date:
            graph = graph.loc[graph["date"] >= pd.Timestamp(args.start_date)]
        if args.end_date:
            graph = graph.loc[graph["date"] <= pd.Timestamp(args.end_date)]
        panel = panel.merge(graph, on=KEY_COLS, how="left", sort=False)
        del graph

    supervised_graph_cols = [c for c in feature_cols if c in SUPERVISED_GRAPH_FEATURES]
    if supervised_graph_cols:
        if not args.supervised_graph_embedding_path:
            raise ValueError(
                "--supervised-graph-embedding-path is required when supervised graph features are included. "
                "Pass the target-matched supervised_gat_oof_embeddings.parquet file."
            )
        supervised_graph_path = Path(args.supervised_graph_embedding_path)
        print(
            f"Joining supervised graph embeddings: {supervised_graph_path} "
            f"({len(supervised_graph_cols)} features)"
        )
        supervised_graph = pd.read_parquet(
            supervised_graph_path,
            columns=KEY_COLS + supervised_graph_cols,
        )
        if args.start_date:
            supervised_graph = supervised_graph.loc[
                supervised_graph["date"] >= pd.Timestamp(args.start_date)
            ]
        if args.end_date:
            supervised_graph = supervised_graph.loc[
                supervised_graph["date"] <= pd.Timestamp(args.end_date)
            ]
        if supervised_graph.duplicated(KEY_COLS).any():
            dupes = int(supervised_graph.duplicated(KEY_COLS).sum())
            raise ValueError(
                f"Supervised graph embeddings contain {dupes} duplicate date/symbol rows: "
                f"{supervised_graph_path}"
            )
        panel = panel.merge(
            supervised_graph,
            on=KEY_COLS,
            how="left",
            sort=False,
        )
        missing_all = panel[supervised_graph_cols].isna().all(axis=1).mean()
        missing_any = panel[supervised_graph_cols].isna().any(axis=1).mean()
        print(
            "Supervised graph embedding missing rows after join: "
            f"all_features={missing_all:.2%}, any_feature={missing_any:.2%}"
        )
        del supervised_graph

    panel = panel.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)
    return panel


def attach_effective_labels(
    panel: pd.DataFrame,
    target_col: str,
    return_col: str,
    horizon_days: int,
    execution_lag_days: int,
) -> pd.DataFrame:
    if execution_lag_days < 0:
        raise ValueError("--execution-lag-days must be >= 0")
    panel = panel.sort_values(["symbol", "date"], kind="mergesort").copy()
    g = panel.groupby("symbol", sort=False, observed=False)
    panel[EVAL_TARGET_COL] = g[target_col].shift(-execution_lag_days)
    panel[RAW_EVAL_TARGET_COL] = panel[EVAL_TARGET_COL]
    panel[EVAL_RETURN_COL] = g[return_col].shift(-execution_lag_days)
    panel[LABEL_END_DATE_COL] = g["date"].shift(-(execution_lag_days + horizon_days))
    panel = panel.dropna(subset=[EVAL_TARGET_COL, EVAL_RETURN_COL, LABEL_END_DATE_COL]).copy()
    return panel.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)


def _standardize_design(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float64, copy=True)
    med = np.nanmedian(x, axis=0)
    med[~np.isfinite(med)] = 0.0
    inds = np.where(~np.isfinite(x))
    if len(inds[0]):
        x[inds] = np.take(med, inds[1])
    mean = np.nanmean(x, axis=0)
    std = np.nanstd(x, axis=0)
    mean[~np.isfinite(mean)] = 0.0
    std[(~np.isfinite(std)) | (std == 0.0)] = 1.0
    x = (x - mean) / std
    x[~np.isfinite(x)] = 0.0
    return x


def residualize_effective_target(
    panel: pd.DataFrame,
    factor_cols: list[str],
    include_sector: bool,
    ridge_alpha: float,
    min_names: int,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Residualize ``_eval_target`` cross-sectionally within each date.

    This implements the Route B research design: the model trains on the portion
    of the effective forward label not explained by same-date OHLCV style
    factors and, optionally, sector dummies. Coefficients are fit independently
    for each date, so no future dates or pooled time-series information are used
    to define the residual target.
    """
    if not factor_cols and not include_sector:
        return panel, {}

    missing = [c for c in factor_cols if c not in panel.columns]
    if missing:
        raise ValueError(
            "Target residualization factors are not present in the loaded panel: "
            + ", ".join(missing)
        )

    out = panel.copy()
    raw = out[EVAL_TARGET_COL].astype("float32")
    out[RAW_EVAL_TARGET_COL] = raw
    residual = pd.Series(np.nan, index=out.index, dtype="float32")
    rows_used = 0
    r2_values: list[float] = []
    alpha = max(float(ridge_alpha), 0.0)

    for _, g in out.groupby("date", sort=True, observed=True):
        y = g[EVAL_TARGET_COL].to_numpy(dtype=np.float64, copy=False)
        valid = np.isfinite(y)
        if factor_cols:
            x_num_all = g[factor_cols].to_numpy(dtype=np.float64, copy=False)
            valid &= np.isfinite(x_num_all).any(axis=1)
        if int(valid.sum()) < max(min_names, len(factor_cols) + 5):
            continue

        idx = g.index[valid]
        yv = y[valid]
        blocks = [np.ones((len(idx), 1), dtype=np.float64)]
        if factor_cols:
            blocks.append(_standardize_design(g.loc[idx, factor_cols].to_numpy(dtype=np.float64)))
        if include_sector and "sector" in g.columns:
            sector = pd.get_dummies(g.loc[idx, "sector"].astype("string"), dtype=np.float64)
            if sector.shape[1] > 1:
                blocks.append(sector.iloc[:, 1:].to_numpy(dtype=np.float64))
        x = np.column_stack(blocks)
        xtx = x.T @ x
        penalty = np.eye(xtx.shape[0], dtype=np.float64) * alpha
        penalty[0, 0] = 0.0
        try:
            beta = np.linalg.solve(xtx + penalty, x.T @ yv)
        except np.linalg.LinAlgError:
            beta = np.linalg.pinv(xtx + penalty) @ (x.T @ yv)
        pred = x @ beta
        resid = yv - pred
        residual.loc[idx] = resid.astype("float32")
        rows_used += len(idx)
        denom = float(np.sum((yv - yv.mean()) ** 2))
        if denom > 0:
            r2_values.append(float(1.0 - np.sum(resid**2) / denom))

    out[EVAL_TARGET_COL] = residual
    before = len(out)
    out = out.dropna(subset=[EVAL_TARGET_COL]).reset_index(drop=True)
    meta: dict[str, object] = {
        "enabled": True,
        "factor_cols": factor_cols,
        "include_sector": bool(include_sector),
        "ridge_alpha": alpha,
        "rows_before": int(before),
        "rows_after": int(len(out)),
        "rows_residualized": int(rows_used),
        "dates_after": int(out["date"].nunique()),
        "mean_daily_r2": float(np.nanmean(r2_values)) if r2_values else math.nan,
        "median_daily_r2": float(np.nanmedian(r2_values)) if r2_values else math.nan,
    }
    print(
        "Target residualization: "
        f"rows={meta['rows_after']}/{meta['rows_before']} "
        f"dates={meta['dates_after']} mean_daily_r2={meta['mean_daily_r2']:.4f}"
    )
    return out, meta


def apply_liquidity_universe(df: pd.DataFrame, liq_col: str, drop_pct: float | None) -> pd.DataFrame:
    """Drop the least-liquid names each date to approximate a tradable universe."""
    if drop_pct is None or drop_pct <= 0:
        return df
    if liq_col not in df.columns:
        print(f"Warning: liquidity column '{liq_col}' not found; skipping liquidity filter.")
        return df
    rank = df.groupby("date", observed=True)[liq_col].rank(pct=True, method="first")
    keep = (rank > drop_pct).to_numpy()
    kept = df.loc[keep].reset_index(drop=True)
    print(
        f"Liquidity filter on '{liq_col}': dropped bottom {drop_pct:.0%} -> "
        f"{len(kept)}/{len(df)} rows kept."
    )
    return kept


def winsorize_by_date(df: pd.DataFrame, cols: list[str], pct: float | None) -> pd.DataFrame:
    """Clip each feature to its per-date [pct, 1-pct] cross-sectional quantiles."""
    if not cols or pct is None or pct <= 0:
        return df
    use_cols = [c for c in cols if c in df.columns]
    if not use_cols:
        return df
    lo = df.groupby("date", observed=True)[use_cols].quantile(pct)
    hi = df.groupby("date", observed=True)[use_cols].quantile(1.0 - pct)
    date_index = pd.Index(df["date"])
    lo_arr = lo.reindex(date_index).to_numpy()
    hi_arr = hi.reindex(date_index).to_numpy()
    lo_arr = np.where(np.isfinite(lo_arr), lo_arr, -np.inf)
    hi_arr = np.where(np.isfinite(hi_arr), hi_arr, np.inf)
    vals = df[use_cols].to_numpy(dtype=np.float32, copy=True)
    np.clip(vals, lo_arr.astype(np.float32), hi_arr.astype(np.float32), out=vals)
    df[use_cols] = vals
    print(f"Winsorized {len(use_cols)} features per date at {pct:.0%}/{1.0 - pct:.0%}.")
    return df


def split_masks(df: pd.DataFrame, train_end: str, val_end: str) -> dict[str, np.ndarray]:
    train_end_ts = pd.Timestamp(train_end)
    val_end_ts = pd.Timestamp(val_end)
    dates = df["date"]
    return {
        "train": (dates <= train_end_ts).to_numpy(),
        "val": ((dates > train_end_ts) & (dates <= val_end_ts)).to_numpy(),
        "test": (dates > val_end_ts).to_numpy(),
    }


def embargo_split_start(
    df: pd.DataFrame,
    mask: np.ndarray,
    embargo_days: int,
) -> np.ndarray:
    if embargo_days <= 0 or not mask.any():
        return mask
    dates = pd.Index(sorted(df.loc[mask, "date"].unique()))
    if len(dates) <= embargo_days:
        return np.zeros_like(mask, dtype=bool)
    cutoff = dates[embargo_days - 1]
    return mask & (df["date"] > cutoff).to_numpy()


def apply_purge_embargo(
    df: pd.DataFrame,
    masks: dict[str, np.ndarray],
    train_end: str,
    val_end: str,
    embargo_days: int,
) -> dict[str, np.ndarray]:
    train_end_ts = pd.Timestamp(train_end)
    val_end_ts = pd.Timestamp(val_end)
    label_end = pd.to_datetime(df[LABEL_END_DATE_COL])
    # The test split has no later boundary, so purge rows whose forward label
    # window extends past the last available trading date (incomplete labels).
    # This is symmetric with the train/val purge and equivalent to the implicit
    # NaN-drop those rows already receive downstream, but made explicit here.
    data_end_ts = pd.Timestamp(df["date"].max())

    purged = {
        "train": masks["train"] & (label_end <= train_end_ts).to_numpy(),
        "val": masks["val"] & (label_end <= val_end_ts).to_numpy(),
        "test": masks["test"] & (label_end <= data_end_ts).to_numpy(),
    }
    purged["val"] = embargo_split_start(df, purged["val"], embargo_days)
    purged["test"] = embargo_split_start(df, purged["test"], embargo_days)
    return purged


def split_audit(df: pd.DataFrame, raw_masks: dict[str, np.ndarray], masks: dict[str, np.ndarray]) -> dict[str, object]:
    audit: dict[str, object] = {}
    for split in ["train", "val", "test"]:
        raw = raw_masks[split]
        kept = masks[split]
        dates = df.loc[kept, "date"]
        label_end = df.loc[kept, LABEL_END_DATE_COL]
        audit[split] = {
            "raw_rows": int(raw.sum()),
            "kept_rows": int(kept.sum()),
            "dropped_rows": int(raw.sum() - kept.sum()),
            "dates": int(dates.nunique()),
            "date_min": None if dates.empty else str(dates.min().date()),
            "date_max": None if dates.empty else str(dates.max().date()),
            "label_end_max": None if label_end.empty else str(pd.Timestamp(label_end.max()).date()),
        }
    return audit


def sample_mask(df: pd.DataFrame, mask: np.ndarray, max_rows: int | None, seed: int) -> np.ndarray:
    """Subsample training rows while keeping whole daily cross-sections intact.

    Cross-sectional models are fit per date, so dropping individual rows from a
    date would distort that day's cross-section. Instead, randomly select whole
    dates (seeded) until the row budget is reached.
    """
    if max_rows is None or int(mask.sum()) <= max_rows:
        return mask
    counts = df.loc[mask].groupby("date", sort=True, observed=True).size()
    rng = np.random.default_rng(seed)
    order = rng.permutation(counts.index.to_numpy())
    cum = np.cumsum(counts.loc[order].to_numpy())
    n_keep = int(np.searchsorted(cum, max_rows, side="right"))
    n_keep = max(n_keep, 1)
    keep_dates = order[:n_keep]
    return mask & df["date"].isin(keep_dates).to_numpy()


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
            device_type=args.lightgbm_device_type,
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
            device=args.xgboost_device,
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
    elif model_name == "mlp":
        hidden = tuple(int(h) for h in str(args.mlp_hidden).split(",") if h.strip())
        model = TorchMLPRegressor(
            hidden=hidden,
            dropout=args.mlp_dropout,
            weight_decay=args.mlp_weight_decay,
            lr=args.mlp_lr,
            epochs=args.mlp_epochs,
            batch_size=args.mlp_batch_size,
            patience=args.mlp_patience,
            seed=args.sample_seed,
        )
    else:
        model = NumpyRidgeRegressor(alpha=args.ridge_alpha)
        model_name = "ridge"

    print(f"Training model: {model_name}")
    model.fit(x_train, y_train)
    return model_name, model


def safe_corrcoef(x: pd.Series, y: pd.Series) -> float:
    x_arr = x.to_numpy(dtype=np.float64, copy=False)
    y_arr = y.to_numpy(dtype=np.float64, copy=False)
    finite = np.isfinite(x_arr) & np.isfinite(y_arr)
    x_arr = x_arr[finite]
    y_arr = y_arr[finite]
    if len(x_arr) < 2 or np.ptp(x_arr) == 0.0 or np.ptp(y_arr) == 0.0:
        return math.nan
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = np.corrcoef(x_arr, y_arr)[0, 1]
    return float(corr) if np.isfinite(corr) else math.nan


def spearman_by_date(df: pd.DataFrame, score_col: str, target_col: str, min_names: int) -> pd.DataFrame:
    rows = []
    for dt, g in df.groupby("date", sort=True):
        g = g[[score_col, target_col]].dropna()
        if len(g) < min_names:
            continue
        rank_corr = safe_corrcoef(g[score_col].rank(), g[target_col].rank())
        pearson_corr = safe_corrcoef(g[score_col], g[target_col])
        rows.append({"date": dt, "rank_ic": rank_corr, "ic": pearson_corr, "n": len(g)})
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
    for _, sg in g.groupby("sector", sort=False, observed=True):
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


def summarize_ic(ic: pd.DataFrame, horizon_days: int = 1) -> dict[str, float]:
    """Summarize the daily rank-IC series.

    For horizons > 1 the daily IC series is autocorrelated because forward return
    windows overlap, which deflates the IC standard deviation and inflates a naive
    ICIR. ``rank_ic_ir`` is therefore computed on a non-overlapping subsample
    (every ``horizon_days`` dates) and annualized by ``252 / horizon_days``. The
    naive overlapping value is kept as ``rank_ic_ir_raw`` for reference only.
    """
    empty = {
        "mean_rank_ic": math.nan,
        "mean_ic": math.nan,
        "rank_ic_std": math.nan,
        "ic_std": math.nan,
        "rank_ic_ir": math.nan,
        "ic_ir": math.nan,
        "rank_ic_ir_raw": math.nan,
        "ic_ir_raw": math.nan,
        "ic_dates": 0,
        "ic_dates_nonoverlap": 0,
    }
    if ic.empty:
        return empty
    horizon_days = max(1, int(horizon_days))
    vals = ic.sort_values("date")["rank_ic"].dropna()
    if vals.empty:
        return empty
    mean = float(vals.mean())
    std_daily = float(vals.std(ddof=1))
    raw_icir = mean / (std_daily + 1e-12) * math.sqrt(252.0)
    nonoverlap = vals.iloc[::horizon_days]
    std_no = float(nonoverlap.std(ddof=1))
    icir_adj = float(nonoverlap.mean()) / (std_no + 1e-12) * math.sqrt(252.0 / horizon_days)
    pearson_vals = ic.sort_values("date").get("ic", pd.Series(dtype="float64")).dropna()
    if pearson_vals.empty:
        pearson_mean = math.nan
        pearson_std = math.nan
        pearson_raw_ir = math.nan
        pearson_ir = math.nan
    else:
        pearson_mean = float(pearson_vals.mean())
        pearson_std = float(pearson_vals.std(ddof=1))
        pearson_raw_ir = pearson_mean / (pearson_std + 1e-12) * math.sqrt(252.0)
        pearson_nonoverlap = pearson_vals.iloc[::horizon_days]
        pearson_no_std = float(pearson_nonoverlap.std(ddof=1))
        pearson_ir = float(pearson_nonoverlap.mean()) / (pearson_no_std + 1e-12) * math.sqrt(
            252.0 / horizon_days
        )
    return {
        "mean_rank_ic": mean,
        "mean_ic": pearson_mean,
        "rank_ic_std": std_daily,
        "ic_std": pearson_std,
        "rank_ic_ir": icir_adj,
        "ic_ir": pearson_ir,
        "rank_ic_ir_raw": raw_icir,
        "ic_ir_raw": pearson_raw_ir,
        "ic_dates": int(len(vals)),
        "ic_dates_nonoverlap": int(len(nonoverlap)),
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


def raw_target_metric_summary(
    df: pd.DataFrame,
    score_col: str,
    target_col: str,
    args: argparse.Namespace,
    periods_per_year: float,
    horizon_days: int,
) -> tuple[dict[str, float], pd.DataFrame, pd.DataFrame]:
    if target_col == RAW_EVAL_TARGET_COL or RAW_EVAL_TARGET_COL not in df.columns:
        return {}, pd.DataFrame(), pd.DataFrame()
    raw_ic = spearman_by_date(df, score_col, RAW_EVAL_TARGET_COL, args.min_names_per_date)
    raw_spread = decile_spread_by_date(
        df, score_col, RAW_EVAL_TARGET_COL, args.long_short_pct, args.min_names_per_date
    )
    out: dict[str, float] = {}
    out.update({f"raw_target_{k}": v for k, v in summarize_ic(raw_ic, horizon_days).items()})
    out.update({f"raw_target_{k}": v for k, v in summarize_spread(raw_spread, periods_per_year).items()})
    return out, raw_ic, raw_spread


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
    horizon_days = int(getattr(args, "label_horizon_days", 1))
    ic = spearman_by_date(df, score_col, target_col, args.min_names_per_date)
    spread = decile_spread_by_date(
        df, score_col, target_col, args.long_short_pct, args.min_names_per_date
    )
    raw_metrics, raw_ic, raw_spread = raw_target_metric_summary(
        df, score_col, target_col, args, periods_per_year, horizon_days
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
    if not raw_ic.empty:
        raw_ic.to_csv(out_dir / f"{score_col}_{split_name}_raw_target_rank_ic.csv", index=False)
    if not raw_spread.empty:
        raw_spread.to_csv(out_dir / f"{score_col}_{split_name}_raw_target_decile_spread.csv", index=False)
    bt.to_csv(out_dir / f"{score_col}_{split_name}_backtest.csv", index=False)
    metrics = {
        **summarize_ic(ic, horizon_days),
        **summarize_spread(spread, periods_per_year),
        **raw_metrics,
        **summarize_backtest(bt, periods_per_year),
        "rows": int(len(df)),
        "dates": int(df["date"].nunique()),
    }
    sharpe = metrics.get("sharpe_net", math.nan)
    icir = metrics.get("rank_ic_ir", math.nan)
    metrics["suspect_overfit_or_leak"] = bool(
        (isinstance(sharpe, float) and math.isfinite(sharpe) and sharpe > 3.0)
        or (isinstance(icir, float) and math.isfinite(icir) and icir > 5.0)
    )
    if metrics["suspect_overfit_or_leak"]:
        print(
            f"  [SANITY] {score_col}/{split_name}: suspect metrics "
            f"(Sharpe={sharpe:.2f}, ICIR={icir:.2f}); check overlap/leakage."
        )
    return metrics


def parse_regime_periods(spec: str | None) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    raw: dict[str, object]
    if spec:
        raw = json.loads(spec)
    else:
        raw = REGIME_PERIODS
    out: dict[str, tuple[pd.Timestamp, pd.Timestamp]] = {}
    for name, bounds in raw.items():
        if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            raise ValueError(f"Regime '{name}' must be [start_date, end_date]")
        out[str(name)] = (pd.Timestamp(bounds[0]), pd.Timestamp(bounds[1]))
    return out


def evaluate_regimes(
    df: pd.DataFrame,
    score_col: str,
    target_col: str,
    return_col: str,
    args: argparse.Namespace,
    out_dir: Path,
    split_name: str,
) -> dict[str, dict[str, float]]:
    regimes = parse_regime_periods(args.regime_periods_json)
    rows = []
    out: dict[str, dict[str, float]] = {}
    dates = pd.to_datetime(df["date"])
    for name, (start, end) in regimes.items():
        sub = df.loc[(dates >= start) & (dates <= end)].copy()
        if sub.empty:
            continue
        metrics = evaluate_score_metrics_only(sub, score_col, target_col, return_col, args)
        out[name] = metrics
        rows.append({"regime": name, "start": str(start.date()), "end": str(end.date()), **metrics})
    if rows:
        pd.DataFrame(rows).to_csv(out_dir / f"{score_col}_{split_name}_regime_metrics.csv", index=False)
    return out


def evaluate_score_metrics_only(
    df: pd.DataFrame,
    score_col: str,
    target_col: str,
    return_col: str,
    args: argparse.Namespace,
) -> dict[str, float]:
    periods_per_year = 252.0 / args.rebalance_every
    horizon_days = int(getattr(args, "label_horizon_days", 1))
    ic = spearman_by_date(df, score_col, target_col, args.min_names_per_date)
    spread = decile_spread_by_date(
        df, score_col, target_col, args.long_short_pct, args.min_names_per_date
    )
    raw_metrics, _, _ = raw_target_metric_summary(
        df, score_col, target_col, args, periods_per_year, horizon_days
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
    return {
        **summarize_ic(ic, horizon_days),
        **summarize_spread(spread, periods_per_year),
        **raw_metrics,
        **summarize_backtest(bt, periods_per_year),
        "rows": int(len(df)),
        "dates": int(df["date"].nunique()),
    }


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        out = float(value)
        return out if math.isfinite(out) else None
    return value


def write_summary_markdown(
    out_path: Path,
    args: argparse.Namespace,
    model_name: str,
    feature_cols: list[str],
    metrics: dict[str, dict[str, object]],
    audit: dict[str, object],
) -> None:
    lines = [
        "# Model Pipeline Summary",
        "",
        f"- Target: `{args.target_col}`",
        f"- Portfolio return column: `{args.return_col}`",
        f"- Model: `{model_name}`",
        f"- Feature variant: `{getattr(args, 'feature_variant_label', 'graph' if args.include_graph_embeddings else 'tabular')}`",
        f"- Feature count: {len(feature_cols)}",
        f"- Graph embedding features: {sum(c in GRAPH_FEATURES for c in feature_cols)}",
        f"- Supervised graph embedding features: {sum(c in SUPERVISED_GRAPH_FEATURES for c in feature_cols)}",
        f"- Train end: {args.train_end}",
        f"- Validation end: {args.val_end}",
        f"- Target horizon: {args.label_horizon_days} trading days",
        f"- Execution lag: {args.execution_lag_days} trading days",
        f"- Embargo: {args.embargo_days_resolved} trading days at val/test starts",
        f"- Rebalance every: {args.rebalance_every} trading days",
        f"- Transaction cost: {args.transaction_cost_bps:.2f} bps per one-way turnover",
        f"- Sector neutral portfolio: {args.sector_neutral}",
        f"- Target residualized against factors: {bool(getattr(args, 'target_residualize_factors', None) or getattr(args, 'target_residualize_sector', False))}",
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
            "## Split Audit",
            "",
            "| split | raw rows | kept rows | dropped | date min | date max | label end max |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for split, row in audit.items():
        lines.append(
            "| {split} | {raw_rows} | {kept_rows} | {dropped_rows} | {date_min} | {date_max} | {label_end_max} |".format(
                split=split,
                raw_rows=row.get("raw_rows", 0),
                kept_rows=row.get("kept_rows", 0),
                dropped_rows=row.get("dropped_rows", 0),
                date_min=row.get("date_min"),
                date_max=row.get("date_max"),
                label_end_max=row.get("label_end_max"),
            )
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Baseline score is a single cross-sectional momentum rank feature.",
            "- Model score is trained only on purged rows up to the configured train split.",
            "- Effective labels and portfolio returns are shifted by the execution lag so same-close trading is not assumed.",
            "- Training and validation rows whose label horizon crosses the next split boundary are removed before fitting or model selection.",
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
    residual_factor_cols = target_residual_factor_columns(args, fmap)
    feature_cols = list(dict.fromkeys(feature_cols + residual_factor_cols))
    if args.include_graph_embeddings:
        feature_cols = list(dict.fromkeys(feature_cols + GRAPH_FEATURES))
    if args.include_supervised_graph_embeddings:
        feature_cols = list(dict.fromkeys(feature_cols + SUPERVISED_GRAPH_FEATURES))
    graph_feature_cols = [c for c in feature_cols if c in GRAPH_FEATURES]
    supervised_graph_feature_cols = [c for c in feature_cols if c in SUPERVISED_GRAPH_FEATURES]
    if args.include_graph_embeddings and args.include_supervised_graph_embeddings:
        feature_variant = "graph_supervised"
    elif args.include_supervised_graph_embeddings:
        feature_variant = "supervised_graph"
    elif args.include_graph_embeddings:
        feature_variant = "graph"
    else:
        feature_variant = "tabular"
    args.feature_variant_label = feature_variant
    panel = load_panel(args, feature_cols, fmap)
    horizon_days = infer_horizon_days(args.target_col, args.return_col)
    embargo_days = resolve_embargo_days(horizon_days, args.embargo_days)
    args.label_horizon_days = horizon_days
    args.embargo_days_resolved = embargo_days
    if args.rebalance_every is None:
        args.rebalance_every = horizon_days
    args.rebalance_every_resolved = args.rebalance_every
    panel = attach_effective_labels(
        panel,
        args.target_col,
        args.return_col,
        horizon_days,
        args.execution_lag_days,
    )
    panel = apply_liquidity_universe(panel, "log_dollar_volume", args.min_dollar_volume_pct)
    panel = winsorize_by_date(panel, feature_cols, args.winsorize_pct)
    target_residualization: dict[str, object] = {}
    if residual_factor_cols or args.target_residualize_sector:
        panel, target_residualization = residualize_effective_target(
            panel,
            residual_factor_cols,
            args.target_residualize_sector,
            args.target_residualize_ridge_alpha,
            args.min_names_per_date,
        )
    print(
        json.dumps(
            {
                "rows": len(panel),
                "dates": int(panel["date"].nunique()),
                "symbols": int(panel["symbol"].nunique()),
                "date_min": str(panel["date"].min().date()),
                "date_max": str(panel["date"].max().date()),
                "features": len(feature_cols),
                "feature_variant": feature_variant,
                "graph_features": len(graph_feature_cols),
                "supervised_graph_features": len(supervised_graph_feature_cols),
            },
            indent=2,
        )
    )

    raw_masks = split_masks(panel, args.train_end, args.val_end)
    masks = apply_purge_embargo(
        panel,
        raw_masks,
        args.train_end,
        args.val_end,
        embargo_days,
    )
    audit = split_audit(panel, raw_masks, masks)
    print(
        json.dumps(
            {
                "label_horizon_days": horizon_days,
                "execution_lag_days": args.execution_lag_days,
                "embargo_days": embargo_days,
                "split_audit": audit,
            },
            indent=2,
        )
    )
    train_fit_mask = sample_mask(panel, masks["train"], args.max_train_rows, args.sample_seed)
    prep = fit_preprocessor(panel, feature_cols, train_fit_mask)
    x_train = prep.transform(panel.loc[train_fit_mask])
    y_train = panel.loc[train_fit_mask, EVAL_TARGET_COL].to_numpy(dtype=np.float32)

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
    regime_metrics: dict[str, dict[str, dict[str, object]]] = {
        "baseline_score": {},
        "model_score": {},
    }
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
                EVAL_TARGET_COL,
                EVAL_RETURN_COL,
                args,
                split,
                out_dir,
            )
            regime_metrics[score_col][split] = evaluate_regimes(
                split_df,
                score_col,
                EVAL_TARGET_COL,
                EVAL_RETURN_COL,
                args,
                out_dir,
                split,
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
        pred_cols = KEY_COLS + META_COLS + [
            args.target_col,
            args.return_col,
            RAW_EVAL_TARGET_COL,
            EVAL_TARGET_COL,
            EVAL_RETURN_COL,
            LABEL_END_DATE_COL,
            "baseline_score",
            "model_score",
        ]
        panel.loc[masks["val"] | masks["test"], pred_cols].to_parquet(
            out_dir / "predictions_val_test.parquet", index=False
        )

    config = vars(args).copy()
    config["run_name"] = run_name
    config["model_resolved"] = model_name
    config["feature_variant"] = feature_variant
    config["feature_count"] = len(feature_cols)
    config["graph_feature_count"] = len(graph_feature_cols)
    config["graph_feature_columns"] = graph_feature_cols
    config["supervised_graph_feature_count"] = len(supervised_graph_feature_cols)
    config["supervised_graph_feature_columns"] = supervised_graph_feature_cols
    config["label_horizon_days"] = horizon_days
    config["embargo_days_resolved"] = embargo_days
    config["split_audit"] = audit
    config["target_residualization"] = target_residualization
    (out_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    pd.DataFrame({"feature": feature_cols}).to_csv(out_dir / "selected_features.csv", index=False)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (out_dir / "regime_metrics.json").write_text(
        json.dumps(clean_json(regime_metrics), indent=2, allow_nan=False), encoding="utf-8"
    )
    write_summary_markdown(out_dir / "summary.md", args, model_name, feature_cols, metrics, audit)
    print(f"Done. Results written to {out_dir}")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
