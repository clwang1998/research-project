#!/usr/bin/env python3
"""Build the final Markdown report from diagnostics and model-grid outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def add_target_parts(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "target_col" not in df.columns:
        return df
    out = df.copy()
    if "horizon" not in out.columns:
        out["horizon"] = (
            out["target_col"]
            .astype(str)
            .str.extract(r"_fwd_(\d+)d$", expand=False)
            .astype("Int64")
        )
    if "target_family" not in out.columns:
        out["target_family"] = (
            out["target_col"]
            .astype(str)
            .str.removeprefix("target_")
            .str.replace(r"_fwd_\d+d$", "", regex=True)
        )
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-name", default="target_grid_core")
    parser.add_argument("--metrics-dir", default="output/model_pipeline")
    parser.add_argument("--diagnostics", default="output/diagnostics/diagnostics_summary.json")
    parser.add_argument("--out", default="docs/experiment_results_report.md")
    return parser.parse_args()


def pct(x: float | None) -> str:
    if x is None or pd.isna(x):
        return "NA"
    return f"{x:.2%}"


def fmt(x: float | None, digits: int = 4) -> str:
    if x is None or pd.isna(x):
        return "NA"
    return f"{x:.{digits}f}"


def load_metrics(metrics_dir: Path, experiment_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_path = metrics_dir / f"{experiment_name}_all_metrics.csv"
    best_path = metrics_dir / f"{experiment_name}_best_metrics.csv"
    all_metrics = pd.read_csv(all_path) if all_path.exists() else pd.DataFrame()
    best_metrics = pd.read_csv(best_path) if best_path.exists() else pd.DataFrame()
    return add_target_parts(all_metrics), add_target_parts(best_metrics)


def best_model_table(best: pd.DataFrame) -> pd.DataFrame:
    if best.empty:
        return pd.DataFrame()
    test = best.loc[(best["score"] == "model_score") & (best["split"] == "test")].copy()
    val = best.loc[(best["score"] == "model_score") & (best["split"] == "val")][
        ["run_name", "mean_rank_ic", "rank_ic_ir", "sharpe_net"]
    ].rename(
        columns={
            "mean_rank_ic": "val_ic",
            "rank_ic_ir": "val_icir",
            "sharpe_net": "val_sharpe",
        }
    )
    out = test.merge(val, on="run_name", how="left")
    keep = [
        "horizon",
        "target_family",
        "target_col",
        "model",
        "grid_tag",
        "val_ic",
        "val_icir",
        "mean_rank_ic",
        "rank_ic_ir",
        "sharpe_net",
        "ann_return_net",
        "avg_turnover",
    ]
    out = out[keep].rename(
        columns={
            "mean_rank_ic": "test_ic",
            "rank_ic_ir": "test_icir",
            "sharpe_net": "test_sharpe",
            "ann_return_net": "test_ann_return",
            "avg_turnover": "test_turnover",
        }
    )
    return out.sort_values(["horizon", "target_family", "model"])


def baseline_comparison(best: pd.DataFrame) -> pd.DataFrame:
    if best.empty:
        return pd.DataFrame()
    test = best.loc[best["split"] == "test"].copy()
    model = test.loc[test["score"] == "model_score"][
        ["run_name", "target_col", "model", "rank_ic_ir", "sharpe_net", "mean_rank_ic"]
    ].rename(
        columns={
            "rank_ic_ir": "model_test_icir",
            "sharpe_net": "model_test_sharpe",
            "mean_rank_ic": "model_test_ic",
        }
    )
    base = test.loc[test["score"] == "baseline_score"][
        ["run_name", "rank_ic_ir", "sharpe_net", "mean_rank_ic"]
    ].rename(
        columns={
            "rank_ic_ir": "baseline_test_icir",
            "sharpe_net": "baseline_test_sharpe",
            "mean_rank_ic": "baseline_test_ic",
        }
    )
    out = model.merge(base, on="run_name", how="left")
    out["delta_icir"] = out["model_test_icir"] - out["baseline_test_icir"]
    out["delta_sharpe"] = out["model_test_sharpe"] - out["baseline_test_sharpe"]
    return out.sort_values(["target_col", "model"])


def model_win_counts(table: pd.DataFrame, metric: str) -> pd.DataFrame:
    if table.empty:
        return pd.DataFrame()
    rows = []
    for target, g in table.groupby("target_col"):
        h = g.dropna(subset=[metric])
        if h.empty:
            continue
        winner = h.sort_values(metric, ascending=False).iloc[0]
        rows.append(
            {
                "target_col": target,
                "winner": winner["model"],
                "metric": metric,
                "value": winner[metric],
            }
        )
    return pd.DataFrame(rows)


def best_params_table(best: pd.DataFrame, metrics_dir: Path) -> pd.DataFrame:
    if best.empty:
        return pd.DataFrame()
    val = best.loc[(best["score"] == "model_score") & (best["split"] == "val")].copy()
    rows = []
    for _, row in val.iterrows():
        config_path = metrics_dir / str(row["run_name"]) / "config.json"
        if not config_path.exists():
            continue
        config = json.loads(config_path.read_text(encoding="utf-8"))
        rows.append(
            {
                "target_col": row["target_col"],
                "model": row["model"],
                "run_name": row["run_name"],
                "val_icir": row["rank_ic_ir"],
                "n_estimators": config.get("n_estimators"),
                "learning_rate": config.get("learning_rate"),
                "max_depth": config.get("max_depth"),
                "num_leaves": config.get("num_leaves"),
                "min_child_samples": config.get("min_child_samples"),
                "min_child_weight": config.get("min_child_weight"),
                "subsample": config.get("subsample"),
                "colsample_bytree": config.get("colsample_bytree"),
                "reg_lambda": config.get("reg_lambda"),
            }
        )
    out = add_target_parts(pd.DataFrame(rows))
    if out.empty:
        return out
    return out.sort_values(["horizon", "target_family", "model"])


def raw_price_table(diagnostics: dict) -> pd.DataFrame:
    rows = diagnostics.get("raw_price_predictability_topline", [])
    return pd.DataFrame(rows)


def write_report(
    all_metrics: pd.DataFrame,
    best: pd.DataFrame,
    diagnostics: dict,
    out_path: Path,
    experiment_name: str,
    metrics_dir: Path,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    best_table = best_model_table(best)
    base_cmp = baseline_comparison(best)
    raw_ic = raw_price_table(diagnostics)
    params = best_params_table(best, metrics_dir)
    if not params.empty:
        params.to_csv(metrics_dir / f"{experiment_name}_best_params.csv", index=False)

    completed_runs = int(all_metrics["run_name"].nunique()) if not all_metrics.empty else 0
    completed_targets = int(all_metrics["target_col"].nunique()) if not all_metrics.empty else 0
    horizons = (
        sorted(int(x) for x in all_metrics["horizon"].dropna().unique())
        if not all_metrics.empty and "horizon" in all_metrics.columns
        else []
    )
    target_families = (
        sorted(str(x) for x in all_metrics["target_family"].dropna().unique())
        if not all_metrics.empty and "target_family" in all_metrics.columns
        else []
    )
    expected_targets = len(horizons) * len(target_families) if horizons and target_families else completed_targets
    completed_models = (
        all_metrics.loc[all_metrics["score"] == "model_score"]
        .groupby(["target_col", "model"])["run_name"]
        .nunique()
        .reset_index()
        if not all_metrics.empty
        else pd.DataFrame()
    )

    dq = diagnostics["data_quality"]
    rd = diagnostics["return_diagnostics"]
    ac = diagnostics["single_stock_autocorr"]
    vc = diagnostics["market_volatility_clustering"]

    simple_beats = base_cmp.loc[base_cmp["model"] == "ridge"] if not base_cmp.empty else pd.DataFrame()
    simple_win_rate = (
        float((simple_beats["delta_icir"] > 0).mean()) if not simple_beats.empty else None
    )

    xgb_vs_ridge = pd.DataFrame()
    if not best_table.empty:
        pivot = best_table.pivot_table(
            index="target_col", columns="model", values=["test_icir", "test_sharpe"], aggfunc="first"
        )
        rows = []
        for target in pivot.index:
            row = {"target_col": target}
            for metric in ["test_icir", "test_sharpe"]:
                if (metric, "xgboost") in pivot and (metric, "ridge") in pivot:
                    row[f"xgb_minus_ridge_{metric}"] = pivot.loc[target, (metric, "xgboost")] - pivot.loc[target, (metric, "ridge")]
            rows.append(row)
        xgb_vs_ridge = pd.DataFrame(rows)

    model_wins = model_win_counts(best_table, "test_icir")

    lines = [
        "# S&P 500 Relative Return Modeling Experiment Report",
        "",
        f"- Experiment: `{experiment_name}`",
        f"- Completed run directories: {completed_runs}",
        f"- Completed targets: {completed_targets}/{expected_targets}",
        "- Target grid: "
        + (
            f"{len(horizons)} horizons ({', '.join(f'{h}D' for h in horizons)}) x "
            f"{len(target_families)} target definitions (`{'`, `'.join(target_families)}`)."
            if horizons and target_families
            else "target definitions inferred from completed runs."
        ),
        "- Models: Ridge reference, LightGBM, XGBoost.",
        "- Selection rule: choose each model's best hyperparameter setting by validation ICIR; report test metrics afterward.",
        "",
        "## 1. 数据是否干净？",
        "",
        f"数据整体可用：{dq['rows']:,} rows, {dq['symbols']} symbols, date range {dq['date_min']} to {dq['date_max']}. "
        f"核心 OHLCV 列无缺失，date-symbol 重复数为 {dq['duplicate_symbol_dates']}。"
        f"需要在报告里披露的小问题是：non-positive volume rows = {dq['non_positive_volume_rows']}, "
        f"OHLC inversion rows = {dq['ohlc_inversion_rows']}。这些问题比例很低，对基于收益率和横截面排序的研究影响有限，但正式生产中应进一步清洗。",
        "",
        "## 2. Raw Price 能不能预测？",
        "",
        "raw close price level 的 1D future-return rank IC 接近 0 且为负，说明价格绝对水平本身不是稳定 alpha。"
        "这也支持不要用 raw price LSTM 直接预测价格路径。",
        "",
    ]
    if not raw_ic.empty:
        lines.append(
            raw_ic.loc[raw_ic["score"].isin(["raw_price_level", "close_lag1"])][
                ["score", "target", "mean_rank_ic", "rank_ic_ir", "dates"]
            ].to_markdown(index=False, floatfmt=".4f")
        )
    lines.extend(
        [
            "",
            "## 3. 为什么要用 Log Return？",
            "",
            f"log return 和 simple return 在日频上数值接近，但 log return 可加。"
            f"本数据中 simple-return std = {rd['simple_return']['std']:.6f}, "
            f"log-return std = {rd['log_return']['std']:.6f}, "
            f"mean absolute difference = {rd['simple_minus_log_abs_mean']:.8f}。"
            f"5D log return 由 1D log return 求和与直接计算的最大误差只有 "
            f"{rd['log_additivity_example']['max_abs_diff_sum_vs_direct_5d']:.12f}。"
            "因此 log return 更适合多期 horizon、滚动特征和风险统计。",
            "",
            "## 4. 单股收益有没有自相关？",
            "",
            f"单股 1D return 的 lag-1 自相关均值为 {ac['mean_ret_autocorr_lag1']:.4f}，接近 0 且略为负，"
            "说明直接用昨日收益预测明日同向收益并不强。"
            f"但 absolute return 的 lag-1 自相关均值为 {ac['mean_abs_ret_autocorr_lag1']:.4f}，"
            f"lag-5 仍为 {ac['mean_abs_ret_autocorr_lag5']:.4f}，说明波动状态比收益方向更有持续性。",
            "",
            "## 5. 市场波动有没有聚集？",
            "",
            f"有。市场 absolute return lag-1 autocorr = {vc['market_abs_ret_autocorr_lag1']:.4f}，"
            f"20D realized volatility lag-1 autocorr = {vc['market_realized_vol_20d_autocorr_lag1']:.4f}。"
            "这说明 volatility clustering 非常明显，使用 volatility、drawdown、market-vol context features 是合理的。",
            "",
            "## 6. 什么是 Baseline？",
            "",
            "本实验的 baseline 是单因子横截面 momentum rank：默认使用 "
            "`cs_rank_mom_252d_skip_21d`。它不训练复杂模型，只按每个交易日的股票动量信号排序，"
            "然后同样做 rank IC、decile spread 和 long-short decile backtest。"
            "baseline 的作用是回答：复杂模型是否真的超过一个简单、可解释、常用的量化信号。",
            "",
            "## 7. 简单模型能不能打败 Baseline？",
            "",
        ]
    )
    if simple_beats.empty:
        lines.append("Ridge reference 结果尚未完整生成。")
    else:
        win_count = int((simple_beats["delta_icir"] > 0).sum())
        total = len(simple_beats)
        lines.append(
            f"按 test ICIR 看，Ridge 在 {win_count}/{total} 个已完成 target-model 对照中超过 baseline，"
            f"win rate = {simple_win_rate:.1%}。下面是 Ridge 相对 baseline 的 test delta："
        )
        lines.append(
            simple_beats[["target_col", "delta_icir", "delta_sharpe", "model_test_ic", "baseline_test_ic"]]
            .to_markdown(index=False, floatfmt=".4f")
        )

    lines.extend(
        [
            "",
            "## 8. XGBoost 是否比 Ridge 好？",
            "",
        ]
    )
    if xgb_vs_ridge.empty:
        lines.append("XGBoost/Ridge 对照尚未完整生成。")
    else:
        icir_wins = int((xgb_vs_ridge["xgb_minus_ridge_test_icir"] > 0).sum()) if "xgb_minus_ridge_test_icir" in xgb_vs_ridge else 0
        total = int(xgb_vs_ridge["xgb_minus_ridge_test_icir"].notna().sum()) if "xgb_minus_ridge_test_icir" in xgb_vs_ridge else 0
        lines.append(
            f"按 test ICIR 看，XGBoost 在 {icir_wins}/{total} 个 target 上超过 Ridge。"
            "是否“更好”不只看 ICIR，还要看 Sharpe、turnover 和稳定性；树模型通常 turnover 更高，"
            "因此交易成本敏感。"
        )
        lines.append(xgb_vs_ridge.to_markdown(index=False, floatfmt=".4f"))

    lines.extend(
        [
            "",
            "## 9. LSTM 是否值得复杂度？",
            "",
            "当前证据不支持优先做 raw-price LSTM。原因：",
            "",
            "- 任务目标是横截面相对收益/排序，不是单只股票价格路径预测。",
            "- raw price level 的 IC 接近 0，直接把价格序列喂给 LSTM 容易学到价格尺度、拆股/股票间不可比性和市场 regime，而不是可交易 alpha。",
            "- 1D return 自相关弱，方向预测信号小；真正持续的是波动，不是收益方向。",
            "- LSTM 需要更复杂的样本构造、序列截面融合、调参和防泄漏流程。对 10 页 take-home 报告来说，LightGBM/XGBoost + time split + long-short backtest 的性价比更高。",
            "",
            "因此报告里可以写：LSTM 是未来扩展方向，但不是本项目主模型。",
            "",
            "## 10. Best Model Results",
            "",
        ]
    )
    if best_table.empty:
        lines.append("Model grid results are not available yet.")
    else:
        lines.append(
            best_table[
                [
                    "horizon",
                    "target_family",
                    "model",
                    "grid_tag",
                    "val_icir",
                    "test_ic",
                    "test_icir",
                    "test_sharpe",
                    "test_ann_return",
                    "test_turnover",
                ]
            ].to_markdown(index=False, floatfmt=".4f")
        )

    lines.extend(["", "## 11. Winner Count By Test ICIR", ""])
    if model_wins.empty:
        lines.append("Winner counts are not available yet.")
    else:
        lines.append(model_wins.to_markdown(index=False, floatfmt=".4f"))
        lines.append("")
        lines.append(model_wins["winner"].value_counts().rename_axis("model").reset_index(name="wins").to_markdown(index=False))

    lines.extend(["", "## 12. Best Hyperparameters", ""])
    if params.empty:
        lines.append("Best hyperparameter table is not available.")
    else:
        param_cols = [
            "horizon",
            "target_family",
            "model",
            "val_icir",
            "n_estimators",
            "learning_rate",
            "max_depth",
            "num_leaves",
            "min_child_samples",
            "min_child_weight",
            "subsample",
            "colsample_bytree",
            "reg_lambda",
        ]
        lines.append(params[param_cols].to_markdown(index=False, floatfmt=".4f"))

    lines.extend(
        [
            "",
            "## 13. Files",
            "",
            f"- Full metrics: `output/model_pipeline/{experiment_name}_all_metrics.csv`",
            f"- Best metrics: `output/model_pipeline/{experiment_name}_best_metrics.csv`",
            f"- Best hyperparameters: `output/model_pipeline/{experiment_name}_best_params.csv`",
            f"- Diagnostics: `output/diagnostics/diagnostics_report.md`",
        ]
    )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    metrics_dir = Path(args.metrics_dir)
    diagnostics = json.loads(Path(args.diagnostics).read_text(encoding="utf-8"))
    all_metrics, best = load_metrics(metrics_dir, args.experiment_name)
    write_report(all_metrics, best, diagnostics, Path(args.out), args.experiment_name, metrics_dir)
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
