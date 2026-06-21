#!/usr/bin/env python3
"""Run post-hoc robustness audits for the alpha pitch.

This script does not train models. It consumes existing prediction/backtest
artifacts and produces the missing research-hygiene outputs that matter for a
PM-style review:

* multiple-testing-aware Sharpe diagnostics (PSR/DSR plus CSCV PBO),
* factor-neutral IC and Fama-MacBeth style attribution using available style
  proxies,
* simple capacity / market-impact sensitivity,
* survivorship-bias haircut sensitivity.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from pathlib import Path
from statistics import NormalDist
from types import SimpleNamespace

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_model_pipeline as rmp  # noqa: E402


DEFAULT_SELECTED_RUN = (
    "output/model_search/"
    "overnight_graph_ablation_mlp_small__target_excess_sector_fwd_10d__"
    "fixed_graph__xgboost__xgb_balanced"
)
DEFAULT_FACTORS = [
    "log_dollar_volume",
    "vol_20d",
    "beta_60d",
    "amihud_20d",
    "ret_5d",
    "mom_252d_skip_21d",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-search-dir", default="output/model_search")
    parser.add_argument("--feature-dir", default="data/processed/features_by_group")
    parser.add_argument("--selected-run-dir", default=DEFAULT_SELECTED_RUN)
    parser.add_argument("--out-dir", default="output/alpha_robustness_audit")
    parser.add_argument("--experiment-prefix", default="overnight_graph_ablation_mlp_small")
    parser.add_argument("--target-col", default="target_excess_sector_fwd_10d")
    parser.add_argument("--return-col", default="target_ret_fwd_10d")
    parser.add_argument("--val-end", default="2021-12-31")
    parser.add_argument("--horizon-days", type=int, default=10)
    parser.add_argument("--overlay-lambda", type=float, default=0.25)
    parser.add_argument("--long-short-pct", type=float, default=0.10)
    parser.add_argument("--min-names-per-date", type=int, default=100)
    parser.add_argument("--transaction-cost-bps", type=float, default=5.0)
    parser.add_argument("--sector-neutral", action="store_true", default=True)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--bootstrap-blocks", type=int, default=3)
    parser.add_argument("--pbo-partitions", type=int, default=8)
    parser.add_argument("--max-pbo-strategies", type=int, default=240)
    parser.add_argument("--factors", nargs="*", default=DEFAULT_FACTORS)
    parser.add_argument(
        "--aums",
        nargs="*",
        type=float,
        default=[10e6, 50e6, 100e6, 250e6, 500e6, 1000e6],
    )
    parser.add_argument("--impact-bps-at-1pct-adv", type=float, default=10.0)
    parser.add_argument(
        "--survivorship-scenarios",
        nargs="*",
        default=["low:0.01:-0.30", "base:0.02:-0.30", "stress:0.05:-0.50"],
        help="Name:annual_delisting_rate:average_delisting_return.",
    )
    parser.add_argument("--random-seed", type=int, default=42)
    return parser.parse_args()


def norm_cdf(x: float) -> float:
    return NormalDist().cdf(x)


def norm_ppf(p: float) -> float:
    p = min(max(p, 1e-12), 1.0 - 1e-12)
    return NormalDist().inv_cdf(p)


def safe_float(value: object) -> float:
    try:
        out = float(value)
    except Exception:
        return math.nan
    return out if math.isfinite(out) else math.nan


def annualized_sharpe(returns: pd.Series | np.ndarray, periods_per_year: float) -> float:
    arr = np.asarray(returns, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 2:
        return math.nan
    vol = arr.std(ddof=1) * math.sqrt(periods_per_year)
    if vol <= 0 or not math.isfinite(vol):
        return math.nan
    return float(arr.mean() * periods_per_year / vol)


def summarize_returns(returns: pd.Series | np.ndarray, periods_per_year: float) -> dict[str, float]:
    arr = pd.Series(np.asarray(returns, dtype=np.float64)).dropna()
    if arr.empty:
        return {
            "periods": 0,
            "ann_return_net": math.nan,
            "ann_vol_net": math.nan,
            "sharpe_net": math.nan,
            "max_drawdown_net": math.nan,
            "final_equity_net": math.nan,
        }
    equity = (1.0 + arr).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    ann_return = float(arr.mean() * periods_per_year)
    ann_vol = float(arr.std(ddof=1) * math.sqrt(periods_per_year))
    return {
        "periods": int(len(arr)),
        "ann_return_net": ann_return,
        "ann_vol_net": ann_vol,
        "sharpe_net": float(ann_return / (ann_vol + 1e-12)),
        "max_drawdown_net": float(drawdown.min()),
        "final_equity_net": float(equity.iloc[-1]),
    }


def skew_kurtosis(arr: np.ndarray) -> tuple[float, float]:
    arr = np.asarray(arr, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 3:
        return math.nan, math.nan
    centered = arr - arr.mean()
    std = centered.std(ddof=0)
    if std <= 0:
        return 0.0, 3.0
    z = centered / std
    return float(np.mean(z**3)), float(np.mean(z**4))


def probabilistic_sharpe_ratio(
    observed_sr: float,
    benchmark_sr: float,
    n_obs: int,
    skewness: float,
    kurtosis: float,
) -> float:
    """Bailey/Lopez de Prado PSR approximation."""
    if n_obs < 2 or not all(math.isfinite(x) for x in [observed_sr, benchmark_sr]):
        return math.nan
    denom = 1.0 - skewness * observed_sr + ((kurtosis - 1.0) / 4.0) * observed_sr**2
    if denom <= 0 or not math.isfinite(denom):
        return math.nan
    z = (observed_sr - benchmark_sr) * math.sqrt(n_obs - 1.0) / math.sqrt(denom)
    return float(norm_cdf(z))


def expected_max_sharpe_under_noise(sr_std: float, n_trials: int) -> float:
    """Expected maximum Sharpe across N independent null trials."""
    if n_trials <= 1 or not math.isfinite(sr_std) or sr_std <= 0:
        return 0.0
    gamma = 0.5772156649015329
    return float(
        sr_std
        * (
            (1.0 - gamma) * norm_ppf(1.0 - 1.0 / n_trials)
            + gamma * norm_ppf(1.0 - 1.0 / (n_trials * math.e))
        )
    )


def bootstrap_sharpe_ci(
    returns: pd.Series,
    periods_per_year: float,
    samples: int,
    block_size: int,
    seed: int,
) -> dict[str, float]:
    arr = returns.dropna().to_numpy(dtype=np.float64)
    if len(arr) < 3:
        return {"sharpe_ci_low": math.nan, "sharpe_ci_high": math.nan}
    rng = np.random.default_rng(seed)
    block_size = max(1, int(block_size))
    n_blocks = int(math.ceil(len(arr) / block_size))
    estimates = []
    starts = np.arange(len(arr))
    for _ in range(samples):
        chosen = rng.choice(starts, size=n_blocks, replace=True)
        sample = np.concatenate([arr[s : min(s + block_size, len(arr))] for s in chosen])
        sample = sample[: len(arr)]
        estimates.append(annualized_sharpe(sample, periods_per_year))
    q = np.nanpercentile(estimates, [2.5, 97.5])
    return {"sharpe_ci_low": float(q[0]), "sharpe_ci_high": float(q[1])}


def zscore_by_date(df: pd.DataFrame, col: str) -> pd.Series:
    def _z(s: pd.Series) -> pd.Series:
        x = s.astype(float)
        std = x.std(ddof=0)
        if not math.isfinite(std) or std <= 0:
            return pd.Series(0.0, index=s.index)
        return (x - x.mean()) / std

    return df.groupby("date", observed=True)[col].transform(_z)


def residualize_by_date(df: pd.DataFrame, y_col: str, x_cols: list[str], out_col: str) -> pd.DataFrame:
    pieces = []
    use_cols = [y_col] + x_cols
    for _, g in df.groupby("date", sort=True, observed=True):
        h = g.dropna(subset=use_cols).copy()
        if len(h) < len(x_cols) + 5:
            h[out_col] = math.nan
            pieces.append(h)
            continue
        y = h[y_col].to_numpy(dtype=np.float64)
        x = h[x_cols].to_numpy(dtype=np.float64)
        x = np.column_stack([np.ones(len(x)), x])
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        h[out_col] = y - x @ coef
        pieces.append(h)
    if not pieces:
        out = df.copy()
        out[out_col] = math.nan
        return out
    return pd.concat(pieces, ignore_index=True)


def add_residual_overlay_score(df: pd.DataFrame, overlay_lambda: float) -> pd.DataFrame:
    out = df.copy()
    out["baseline_z"] = zscore_by_date(out, "baseline_score")
    out["model_z"] = zscore_by_date(out, "model_score")
    out = residualize_by_date(out, "model_z", ["baseline_z"], "model_resid_z_raw")
    out["model_resid_z"] = zscore_by_date(out, "model_resid_z_raw")
    out["residual_overlay_score"] = out["baseline_z"] + overlay_lambda * out["model_resid_z"]
    return out


def split_predictions(pred: pd.DataFrame, val_end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    cutoff = pd.Timestamp(val_end)
    pred = pred.copy()
    pred["date"] = pd.to_datetime(pred["date"])
    return pred.loc[pred["date"] <= cutoff].copy(), pred.loc[pred["date"] > cutoff].copy()


def eval_score(
    frame: pd.DataFrame,
    score_col: str,
    args: argparse.Namespace,
) -> tuple[dict[str, float], pd.DataFrame, pd.DataFrame]:
    cfg = SimpleNamespace(
        min_names_per_date=args.min_names_per_date,
        long_short_pct=args.long_short_pct,
        rebalance_every=args.horizon_days,
        transaction_cost_bps=args.transaction_cost_bps,
        sector_neutral=args.sector_neutral,
        label_horizon_days=args.horizon_days,
    )
    ic = rmp.spearman_by_date(frame, score_col, rmp.EVAL_TARGET_COL, cfg.min_names_per_date)
    bt = rmp.run_backtest(
        frame,
        score_col,
        rmp.EVAL_RETURN_COL,
        cfg.long_short_pct,
        cfg.rebalance_every,
        cfg.transaction_cost_bps,
        cfg.min_names_per_date,
        cfg.sector_neutral,
    )
    periods = 252.0 / cfg.rebalance_every
    metrics = {
        **rmp.summarize_ic(ic, cfg.label_horizon_days),
        **rmp.summarize_backtest(bt, periods),
    }
    return metrics, ic, bt


def load_trials_metrics(model_search_dir: Path) -> pd.DataFrame:
    frames = []
    for path in sorted(model_search_dir.glob("*_all_metrics.csv")):
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        df["source_file"] = path.name
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def infer_trial_counts(all_metrics: pd.DataFrame, target_col: str) -> dict[str, int]:
    if all_metrics.empty:
        return {"trial_count_all": 1, "trial_count_same_target": 1}
    df = all_metrics.copy()
    if "split" in df.columns:
        df = df.loc[df["split"].astype(str).eq("test")]
    keys = [c for c in ["run_name", "ensemble_name", "score", "model_weight", "ewma_span", "no_trade_band", "overlay_lambda"] if c in df.columns]
    if not keys:
        keys = [c for c in ["target_col", "model", "feature_variant", "grid_tag"] if c in df.columns]
    all_count = int(max(1, df[keys].astype(str).drop_duplicates().shape[0])) if keys else int(max(1, len(df)))
    same = df.loc[df.get("target_col", pd.Series(index=df.index, dtype=object)).astype(str).eq(target_col)]
    same_count = int(max(1, same[keys].astype(str).drop_duplicates().shape[0])) if keys and not same.empty else 1
    return {"trial_count_all": all_count, "trial_count_same_target": same_count}


def build_return_matrix(model_search_dir: Path, experiment_prefix: str, max_strategies: int) -> pd.DataFrame:
    series = {}
    for path in sorted(model_search_dir.glob(f"{experiment_prefix}__*/model_score_test_backtest.csv")):
        run_name = path.parent.name
        try:
            bt = pd.read_csv(path, parse_dates=["date"])
        except Exception:
            continue
        if {"date", "net_return"}.issubset(bt.columns) and bt["net_return"].notna().sum() >= 10:
            series[run_name] = bt.set_index("date")["net_return"].rename(run_name)
        if len(series) >= max_strategies:
            break
    if not series:
        return pd.DataFrame()
    matrix = pd.concat(series.values(), axis=1).sort_index()
    return matrix.dropna(axis=1, how="all").fillna(0.0)


def cscv_pbo(return_matrix: pd.DataFrame, periods_per_year: float, partitions: int) -> dict[str, float]:
    if return_matrix.empty or return_matrix.shape[1] < 2:
        return {"pbo": math.nan, "pbo_splits": 0, "median_test_percentile": math.nan}
    matrix = return_matrix.copy().sort_index()
    partitions = max(4, min(int(partitions), len(matrix)))
    if partitions % 2:
        partitions -= 1
    blocks = np.array_split(np.arange(len(matrix)), partitions)
    lambdas = []
    ranks = []
    split_ids = range(partitions)
    for train_blocks in itertools.combinations(split_ids, partitions // 2):
        train_idx = np.concatenate([blocks[i] for i in train_blocks])
        test_idx = np.concatenate([blocks[i] for i in split_ids if i not in train_blocks])
        train_scores = matrix.iloc[train_idx].apply(annualized_sharpe, periods_per_year=periods_per_year)
        train_scores = train_scores.replace([np.inf, -np.inf], np.nan).dropna()
        if train_scores.empty:
            continue
        selected = train_scores.idxmax()
        test_scores = matrix.iloc[test_idx].apply(annualized_sharpe, periods_per_year=periods_per_year)
        test_scores = test_scores.replace([np.inf, -np.inf], np.nan).dropna()
        if selected not in test_scores or len(test_scores) < 2:
            continue
        rank_pct = float(test_scores.rank(method="average", pct=True)[selected])
        rank_pct = min(max(rank_pct, 1e-6), 1.0 - 1e-6)
        ranks.append(rank_pct)
        lambdas.append(math.log(rank_pct / (1.0 - rank_pct)))
    if not lambdas:
        return {"pbo": math.nan, "pbo_splits": 0, "median_test_percentile": math.nan}
    lambdas_arr = np.asarray(lambdas, dtype=float)
    return {
        "pbo": float(np.mean(lambdas_arr < 0.0)),
        "pbo_splits": int(len(lambdas_arr)),
        "median_test_percentile": float(np.median(ranks)),
    }


def find_feature_files(feature_dir: Path, columns: list[str]) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in sorted(feature_dir.glob("*.parquet")):
        try:
            import pyarrow.parquet as pq

            cols = pq.ParquetFile(path).schema.names
        except Exception:
            try:
                cols = pd.read_parquet(path, nrows=1).columns
            except Exception:
                continue
        for col in columns:
            if col in cols and col not in found:
                found[col] = path
    return found


def load_feature_columns(feature_dir: Path, columns: list[str], date_min: pd.Timestamp, date_max: pd.Timestamp) -> pd.DataFrame:
    found = find_feature_files(feature_dir, columns)
    by_file: dict[Path, list[str]] = {}
    for col, path in found.items():
        by_file.setdefault(path, []).append(col)
    panel: pd.DataFrame | None = None
    for path, cols in by_file.items():
        read_cols = rmp.KEY_COLS + cols
        part = pd.read_parquet(path, columns=read_cols)
        part["date"] = pd.to_datetime(part["date"])
        part = part.loc[(part["date"] >= date_min) & (part["date"] <= date_max)].copy()
        panel = part if panel is None else panel.merge(part, on=rmp.KEY_COLS, how="outer")
    if panel is None:
        return pd.DataFrame(columns=rmp.KEY_COLS)
    missing = [c for c in columns if c not in panel.columns]
    for col in missing:
        panel[col] = math.nan
    return panel


def factor_neutral_analysis(
    test: pd.DataFrame,
    feature_dir: Path,
    factors: list[str],
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    date_min, date_max = test["date"].min(), test["date"].max()
    factor_panel = load_feature_columns(feature_dir, factors, date_min, date_max)
    merged = test.merge(factor_panel, on=rmp.KEY_COLS, how="left", sort=False)
    available = [c for c in factors if c in merged.columns and merged[c].notna().any()]
    for col in ["residual_overlay_score"] + available:
        merged[f"z_{col}"] = zscore_by_date(merged, col)
    z_factors = [f"z_{c}" for c in available]
    merged = residualize_by_date(
        merged,
        "z_residual_overlay_score",
        z_factors,
        "factor_neutral_score",
    )
    rows = []
    for score_col, label in [
        ("residual_overlay_score", "raw_residual_overlay"),
        ("factor_neutral_score", "factor_neutral_overlay"),
    ]:
        metrics, ic, _ = eval_score(merged, score_col, args)
        rows.append({"signal": label, "n_factors": len(available), **metrics})
        ic_path = None
    fmb_rows = []
    use_cols = ["z_residual_overlay_score"] + z_factors + [rmp.EVAL_TARGET_COL]
    for dt, g in merged.dropna(subset=use_cols).groupby("date", sort=True, observed=True):
        if len(g) < len(use_cols) + args.min_names_per_date:
            continue
        y = g[rmp.EVAL_TARGET_COL].to_numpy(dtype=np.float64)
        x = g[["z_residual_overlay_score"] + z_factors].to_numpy(dtype=np.float64)
        x = np.column_stack([np.ones(len(x)), x])
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        fmb_rows.append({"date": dt, "signal_coef": coef[1], "n": len(g)})
    fmb = pd.DataFrame(fmb_rows)
    if fmb.empty:
        fmb_summary = pd.DataFrame(
            [{"coef_mean": math.nan, "coef_tstat_nonoverlap": math.nan, "coef_dates": 0}]
        )
    else:
        coef_no = fmb.sort_values("date")["signal_coef"].iloc[:: args.horizon_days]
        tstat = float(coef_no.mean() / (coef_no.std(ddof=1) / math.sqrt(len(coef_no)) + 1e-12))
        fmb_summary = pd.DataFrame(
            [
                {
                    "coef_mean": float(coef_no.mean()),
                    "coef_tstat_nonoverlap": tstat,
                    "coef_dates": int(len(coef_no)),
                    "factors": ",".join(available),
                }
            ]
        )
    return pd.DataFrame(rows), fmb_summary


def run_capacity_curve(
    test: pd.DataFrame,
    feature_dir: Path,
    args: argparse.Namespace,
) -> pd.DataFrame:
    date_min, date_max = test["date"].min(), test["date"].max()
    liq = load_feature_columns(feature_dir, ["dollar_volume", "log_dollar_volume"], date_min, date_max)
    frame = test.merge(liq, on=rmp.KEY_COLS, how="left", sort=False)
    if "dollar_volume" not in frame.columns or frame["dollar_volume"].isna().all():
        if "log_dollar_volume" in frame.columns:
            frame["dollar_volume"] = np.exp(frame["log_dollar_volume"].clip(upper=30))
        else:
            frame["dollar_volume"] = math.nan
    unique_dates = pd.Index(sorted(frame["date"].unique()))
    rebalance_dates = unique_dates[:: args.horizon_days]
    prev_w = pd.Series(dtype=np.float64)
    rows_by_aum = {aum: [] for aum in args.aums}
    for dt in rebalance_dates:
        g = frame.loc[
            frame["date"].eq(dt),
            ["symbol", "sector", "residual_overlay_score", rmp.EVAL_RETURN_COL, "dollar_volume"],
        ].dropna(subset=["symbol", "sector", "residual_overlay_score", rmp.EVAL_RETURN_COL])
        if len(g) < args.min_names_per_date:
            continue
        weights = rmp.choose_weights(
            g,
            "residual_overlay_score",
            args.long_short_pct,
            args.min_names_per_date,
            args.sector_neutral,
        )
        if weights.empty:
            continue
        returns = g.set_index("symbol")[rmp.EVAL_RETURN_COL]
        adv = g.set_index("symbol")["dollar_volume"].replace([np.inf, -np.inf], np.nan)
        gross_ret = float((weights * returns.reindex(weights.index)).sum())
        all_idx = weights.index.union(prev_w.index)
        delta = weights.reindex(all_idx, fill_value=0.0) - prev_w.reindex(all_idx, fill_value=0.0)
        turnover = 0.5 * float(delta.abs().sum())
        for aum in args.aums:
            adv_i = adv.reindex(all_idx).fillna(adv.median())
            trade_dollars = delta.abs() * aum
            participation = (trade_dollars / adv_i.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
            impact_bps = args.impact_bps_at_1pct_adv * np.sqrt(np.maximum(participation, 0.0) / 0.01)
            weighted_cost_bps = args.transaction_cost_bps + impact_bps
            total_cost = 0.5 * float((delta.abs() * weighted_cost_bps / 10000.0).sum())
            rows_by_aum[aum].append(
                {
                    "date": dt,
                    "gross_return": gross_ret,
                    "turnover": turnover,
                    "cost": total_cost,
                    "net_return": gross_ret - total_cost,
                    "avg_participation": float(participation[delta.abs() > 0].mean())
                    if (delta.abs() > 0).any()
                    else 0.0,
                    "p95_participation": float(participation[delta.abs() > 0].quantile(0.95))
                    if (delta.abs() > 0).any()
                    else 0.0,
                }
            )
        prev_w = weights
    periods_per_year = 252.0 / args.horizon_days
    out_rows = []
    for aum, rows in rows_by_aum.items():
        bt = pd.DataFrame(rows)
        summary = summarize_returns(bt["net_return"] if not bt.empty else [], periods_per_year)
        out_rows.append(
            {
                "aum": aum,
                **summary,
                "avg_turnover": float(bt["turnover"].mean()) if not bt.empty else math.nan,
                "avg_cost": float(bt["cost"].mean()) if not bt.empty else math.nan,
                "avg_participation": float(bt["avg_participation"].mean()) if not bt.empty else math.nan,
                "p95_participation": float(bt["p95_participation"].quantile(0.95)) if not bt.empty else math.nan,
            }
        )
    return pd.DataFrame(out_rows)


def survivorship_haircut(bt: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    periods_per_year = 252.0 / args.horizon_days
    rows = []
    if bt.empty:
        return pd.DataFrame()
    affected_book_weight = 0.5
    for item in args.survivorship_scenarios:
        name, rate, loss = item.split(":")
        annual_rate = float(rate)
        avg_delisting_return = float(loss)
        annual_haircut = affected_book_weight * annual_rate * abs(avg_delisting_return)
        period_haircut = annual_haircut / periods_per_year
        adjusted = bt["net_return"] - period_haircut
        rows.append(
            {
                "scenario": name,
                "annual_delisting_rate": annual_rate,
                "avg_delisting_return": avg_delisting_return,
                "annual_haircut": annual_haircut,
                **summarize_returns(adjusted, periods_per_year),
            }
        )
    return pd.DataFrame(rows)


def write_markdown(
    out_path: Path,
    summary: dict[str, object],
    selected_metrics: pd.DataFrame,
    multiple_testing: pd.DataFrame,
    pbo: pd.DataFrame,
    factor_ic: pd.DataFrame,
    fmb: pd.DataFrame,
    capacity: pd.DataFrame,
    survivorship: pd.DataFrame,
) -> None:
    def md_table(df: pd.DataFrame, cols: list[str] | None = None, floatfmt: str = ".4f") -> str:
        if df.empty:
            return "_No rows._"
        view = df.copy()
        if cols:
            view = view[cols]
        return view.to_markdown(index=False, floatfmt=floatfmt)

    lines = [
        "# P0 Alpha Robustness Audit",
        "",
        "This audit is post-training only. It uses existing prediction and backtest artifacts.",
        "",
        "## Selected Signal",
        "",
        md_table(selected_metrics),
        "",
        "## Multiple-Testing Diagnostics",
        "",
        md_table(multiple_testing),
        "",
        md_table(pbo),
        "",
        "Interpretation: DSR below 95% or high PBO means the selected Sharpe should be presented as fragile / exploratory rather than a production-grade alpha claim.",
        "",
        "## Factor Attribution",
        "",
        md_table(factor_ic),
        "",
        md_table(fmb),
        "",
        "The factor-neutral row residualizes the final score against available style proxies by date. This is not a full Barra/Fama-French risk model, but it is a quantitative check that was missing from the report.",
        "",
        "## Capacity / Impact Sensitivity",
        "",
        md_table(capacity),
        "",
        "Impact model: base explicit cost plus square-root impact calibrated to the configured bps at 1% ADV participation. Treat this as a capacity stress test, not an execution model.",
        "",
        "## Survivorship Haircut",
        "",
        md_table(survivorship),
        "",
        "The haircut is an adverse directional sensitivity overlay because the dataset lacks historical constituents and delisting returns. It applies annual delisting rate times average delisting loss to half the book; for a long-short momentum tilt the true sign is not proven without point-in-time constituents and delisting returns.",
        "",
        "## Run Metadata",
        "",
        "```json",
        json.dumps(summary, indent=2, sort_keys=True),
        "```",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    selected_run = Path(args.selected_run_dir)
    pred_path = selected_run / "predictions_val_test.parquet"
    if not pred_path.exists():
        raise FileNotFoundError(pred_path)
    pred = pd.read_parquet(pred_path)
    pred["date"] = pd.to_datetime(pred["date"])
    pred = add_residual_overlay_score(pred, args.overlay_lambda)
    val, test = split_predictions(pred, args.val_end)
    selected_rows = []
    for split_name, frame in [("val", val), ("test", test)]:
        for score_col, label in [
            ("baseline_score", "momentum_baseline"),
            ("model_score", "model_score"),
            ("residual_overlay_score", "residual_overlay"),
        ]:
            metrics, _, bt = eval_score(frame, score_col, args)
            selected_rows.append({"split": split_name, "signal": label, **metrics})
            if split_name == "test" and label == "residual_overlay":
                overlay_bt = bt.copy()
    selected_metrics = pd.DataFrame(selected_rows)
    selected_metrics.to_csv(out_dir / "selected_signal_metrics.csv", index=False)
    overlay_bt.to_csv(out_dir / "residual_overlay_test_backtest.csv", index=False)

    periods_per_year = 252.0 / args.horizon_days
    returns = overlay_bt["net_return"].dropna()
    obs_sr = annualized_sharpe(returns, periods_per_year)
    skewness, kurt = skew_kurtosis(returns.to_numpy())
    trial_metrics = load_trials_metrics(Path(args.model_search_dir))
    trial_counts = infer_trial_counts(trial_metrics, args.target_col)
    trial_srs = trial_metrics.loc[
        (trial_metrics.get("split", pd.Series(dtype=object)).astype(str).eq("test"))
        & trial_metrics.get("sharpe_net", pd.Series(dtype=float)).notna(),
        "sharpe_net",
    ].astype(float)
    sr_std = float(trial_srs.std(ddof=1)) if len(trial_srs) > 1 else 1.0 / math.sqrt(max(2, len(returns)))
    ci = bootstrap_sharpe_ci(
        returns,
        periods_per_year,
        args.bootstrap_samples,
        args.bootstrap_blocks,
        args.random_seed,
    )
    mt_rows = []
    for key, n_trials in trial_counts.items():
        sr_star = expected_max_sharpe_under_noise(sr_std, n_trials)
        mt_rows.append(
            {
                "trial_scope": key,
                "n_trials": n_trials,
                "observed_sharpe": obs_sr,
                "trial_sharpe_std": sr_std,
                "expected_max_null_sharpe": sr_star,
                "psr_vs_zero": probabilistic_sharpe_ratio(obs_sr, 0.0, len(returns), skewness, kurt),
                "dsr": probabilistic_sharpe_ratio(obs_sr, sr_star, len(returns), skewness, kurt),
                **ci,
            }
        )
    multiple_testing = pd.DataFrame(mt_rows)
    multiple_testing.to_csv(out_dir / "multiple_testing_dsr.csv", index=False)

    return_matrix = build_return_matrix(
        Path(args.model_search_dir),
        args.experiment_prefix,
        args.max_pbo_strategies,
    )
    pbo_summary = pd.DataFrame(
        [
            {
                "experiment_prefix": args.experiment_prefix,
                "strategies": int(return_matrix.shape[1]),
                **cscv_pbo(return_matrix, periods_per_year, args.pbo_partitions),
            }
        ]
    )
    pbo_summary.to_csv(out_dir / "pbo_cscv.csv", index=False)

    factor_ic, fmb = factor_neutral_analysis(test, Path(args.feature_dir), args.factors, args)
    factor_ic.to_csv(out_dir / "factor_neutral_ic.csv", index=False)
    fmb.to_csv(out_dir / "fama_macbeth_proxy.csv", index=False)

    capacity = run_capacity_curve(test, Path(args.feature_dir), args)
    capacity.to_csv(out_dir / "capacity_curve.csv", index=False)

    survivorship = survivorship_haircut(overlay_bt, args)
    survivorship.to_csv(out_dir / "survivorship_haircut.csv", index=False)

    run_summary = {
        "selected_run_dir": str(selected_run),
        "prediction_path": str(pred_path),
        "target_col": args.target_col,
        "return_col": args.return_col,
        "overlay_lambda": args.overlay_lambda,
        "val_end": args.val_end,
        "horizon_days": args.horizon_days,
        "factor_proxies": args.factors,
    }
    (out_dir / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
    write_markdown(
        out_dir / "p0_alpha_robustness_audit.md",
        run_summary,
        selected_metrics,
        multiple_testing,
        pbo_summary,
        factor_ic,
        fmb,
        capacity,
        survivorship,
    )
    print(json.dumps({"out_dir": str(out_dir), **run_summary}, indent=2))


if __name__ == "__main__":
    main()
