#!/usr/bin/env python3
"""Run target/model grid experiments and aggregate the results.

The script is intentionally resumable: if a run directory already contains
``metrics.json`` and ``config.json``, it is skipped and included in the final
summary.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd


HORIZONS = [1, 5, 20, 30, 40, 50, 60]
TARGET_FAMILIES = ["ret", "excess_market", "rank", "excess_sector"]

RIDGE_GRID = [
    {
        "tag": "ridge_ref",
        "args": ["--model", "ridge", "--ridge-alpha", "25"],
    }
]

LIGHTGBM_GRID = [
    {
        "tag": "lgbm_balanced",
        "args": [
            "--model",
            "lightgbm",
            "--n-estimators",
            "350",
            "--learning-rate",
            "0.04",
            "--max-depth",
            "5",
            "--num-leaves",
            "31",
            "--min-child-samples",
            "250",
            "--subsample",
            "0.75",
            "--colsample-bytree",
            "0.75",
            "--reg-lambda",
            "10",
        ],
    },
    {
        "tag": "lgbm_shallow_regularized",
        "args": [
            "--model",
            "lightgbm",
            "--n-estimators",
            "500",
            "--learning-rate",
            "0.025",
            "--max-depth",
            "4",
            "--num-leaves",
            "15",
            "--min-child-samples",
            "400",
            "--subsample",
            "0.8",
            "--colsample-bytree",
            "0.7",
            "--reg-lambda",
            "20",
        ],
    },
    {
        "tag": "lgbm_deeper",
        "args": [
            "--model",
            "lightgbm",
            "--n-estimators",
            "300",
            "--learning-rate",
            "0.05",
            "--max-depth",
            "6",
            "--num-leaves",
            "63",
            "--min-child-samples",
            "180",
            "--subsample",
            "0.75",
            "--colsample-bytree",
            "0.85",
            "--reg-lambda",
            "8",
        ],
    },
]

XGBOOST_GRID = [
    {
        "tag": "xgb_balanced",
        "args": [
            "--model",
            "xgboost",
            "--n-estimators",
            "350",
            "--learning-rate",
            "0.04",
            "--max-depth",
            "4",
            "--min-child-weight",
            "40",
            "--subsample",
            "0.75",
            "--colsample-bytree",
            "0.75",
            "--reg-lambda",
            "10",
        ],
    },
    {
        "tag": "xgb_shallow_regularized",
        "args": [
            "--model",
            "xgboost",
            "--n-estimators",
            "500",
            "--learning-rate",
            "0.025",
            "--max-depth",
            "3",
            "--min-child-weight",
            "80",
            "--subsample",
            "0.8",
            "--colsample-bytree",
            "0.7",
            "--reg-lambda",
            "20",
        ],
    },
    {
        "tag": "xgb_deeper",
        "args": [
            "--model",
            "xgboost",
            "--n-estimators",
            "300",
            "--learning-rate",
            "0.05",
            "--max-depth",
            "5",
            "--min-child-weight",
            "30",
            "--subsample",
            "0.75",
            "--colsample-bytree",
            "0.85",
            "--reg-lambda",
            "8",
        ],
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--pipeline", default="scripts/run_model_pipeline.py")
    parser.add_argument("--out-dir", default="output/model_pipeline")
    parser.add_argument("--experiment-name", default="target_grid")
    parser.add_argument("--feature-set", default="core", choices=["core", "all"])
    parser.add_argument("--train-end", default="2018-12-31")
    parser.add_argument("--val-end", default="2020-12-31")
    parser.add_argument("--start-date", default="2005-01-01")
    parser.add_argument("--rebalance-every", default="5")
    parser.add_argument("--transaction-cost-bps", default="5")
    parser.add_argument("--n-jobs", default="-1")
    parser.add_argument("--max-train-rows", default=None)
    parser.add_argument("--max-eval-rows", default=None)
    parser.add_argument(
        "--models",
        nargs="+",
        default=["ridge", "lightgbm", "xgboost"],
        choices=["ridge", "lightgbm", "xgboost"],
    )
    parser.add_argument(
        "--horizons",
        nargs="+",
        type=int,
        default=HORIZONS,
    )
    parser.add_argument(
        "--families",
        nargs="+",
        default=TARGET_FAMILIES,
        choices=TARGET_FAMILIES,
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def target_name(family: str, horizon: int) -> str:
    return f"target_{family}_fwd_{horizon}d"


def return_name(horizon: int) -> str:
    return f"target_ret_fwd_{horizon}d"


def grids_for_model(model: str) -> list[dict[str, Any]]:
    if model == "ridge":
        return RIDGE_GRID
    if model == "lightgbm":
        return LIGHTGBM_GRID
    if model == "xgboost":
        return XGBOOST_GRID
    raise ValueError(model)


def run_done(run_dir: Path) -> bool:
    return (run_dir / "metrics.json").exists() and (run_dir / "config.json").exists()


def safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if pd.notna(out) else None


def extract_rows(out_root: Path, experiment_name: str) -> pd.DataFrame:
    rows = []
    for metrics_path in sorted(out_root.glob(f"{experiment_name}__*/metrics.json")):
        run_dir = metrics_path.parent
        config_path = run_dir / "config.json"
        if not config_path.exists():
            continue
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        config = json.loads(config_path.read_text(encoding="utf-8"))
        for score_name, by_split in metrics.items():
            if not isinstance(by_split, dict):
                continue
            for split, vals in by_split.items():
                if not isinstance(vals, dict):
                    continue
                rows.append(
                    {
                        "run_name": run_dir.name,
                        "model": config.get("model_resolved", config.get("model")),
                        "grid_tag": run_dir.name.split("__")[-1],
                        "target_col": config.get("target_col"),
                        "return_col": config.get("return_col"),
                        "horizon": int(str(config.get("target_col", "")).split("_")[-1].replace("d", ""))
                        if str(config.get("target_col", "")).endswith("d")
                        else None,
                        "target_family": str(config.get("target_col", ""))
                        .removeprefix("target_")
                        .rsplit("_fwd_", 1)[0],
                        "score": score_name,
                        "split": split,
                        "mean_rank_ic": safe_float(vals.get("mean_rank_ic")),
                        "rank_ic_ir": safe_float(vals.get("rank_ic_ir")),
                        "mean_top_bottom_spread": safe_float(vals.get("mean_top_bottom_spread")),
                        "spread_ir": safe_float(vals.get("spread_ir")),
                        "ann_return_net": safe_float(vals.get("ann_return_net")),
                        "ann_vol_net": safe_float(vals.get("ann_vol_net")),
                        "sharpe_net": safe_float(vals.get("sharpe_net")),
                        "max_drawdown_net": safe_float(vals.get("max_drawdown_net")),
                        "avg_turnover": safe_float(vals.get("avg_turnover")),
                        "avg_cost": safe_float(vals.get("avg_cost")),
                        "rows": vals.get("rows"),
                        "dates": vals.get("dates"),
                    }
                )
    return pd.DataFrame(rows)


def select_best(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    model_rows = summary.loc[
        (summary["score"] == "model_score") & (summary["split"] == "val")
    ].copy()
    if model_rows.empty:
        return model_rows
    model_rows["rank_key"] = model_rows["rank_ic_ir"].fillna(-1e9)
    idx = model_rows.groupby(["target_col", "model"], dropna=False)["rank_key"].idxmax()
    best_val = model_rows.loc[idx].drop(columns=["rank_key"]).copy()
    keys = best_val[["run_name"]].drop_duplicates()
    best_all = summary.merge(keys, on="run_name", how="inner")
    return best_all.sort_values(["target_col", "model", "score", "split"])


def write_report(summary: pd.DataFrame, best: pd.DataFrame, out_root: Path, experiment_name: str) -> None:
    report_path = out_root / f"{experiment_name}_report.md"
    lines = [
        "# Target Grid Experiment Report",
        "",
        f"- Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Experiment name: `{experiment_name}`",
        f"- Total metric rows: {len(summary)}",
        "",
        "## Best Configs By Validation ICIR",
        "",
    ]
    best_model_test = best.loc[
        (best["score"] == "model_score") & (best["split"] == "test")
    ].copy()
    best_model_val = best.loc[
        (best["score"] == "model_score") & (best["split"] == "val")
    ][["run_name", "rank_ic_ir", "mean_rank_ic", "sharpe_net"]].rename(
        columns={
            "rank_ic_ir": "val_icir",
            "mean_rank_ic": "val_ic",
            "sharpe_net": "val_sharpe",
        }
    )
    merged = best_model_test.merge(best_model_val, on="run_name", how="left")
    if merged.empty:
        lines.append("_No completed model runs yet._")
    else:
        cols = [
            "target_col",
            "model",
            "grid_tag",
            "val_ic",
            "val_icir",
            "val_sharpe",
            "mean_rank_ic",
            "rank_ic_ir",
            "sharpe_net",
            "ann_return_net",
            "avg_turnover",
        ]
        show = merged[cols].sort_values(["target_col", "model"])
        lines.append(show.to_markdown(index=False, floatfmt=".4f"))

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Best configs are selected using validation ICIR only.",
            "- Test results are reported after selection and should be treated as out-of-sample evidence.",
            "- Portfolio PnL always uses the raw forward return for the same horizon.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    tasks = []
    for horizon in args.horizons:
        for family in args.families:
            target = target_name(family, horizon)
            ret = return_name(horizon)
            for model in args.models:
                for spec in grids_for_model(model):
                    run_name = (
                        f"{args.experiment_name}__{target}__{model}__{spec['tag']}"
                    )
                    tasks.append((horizon, family, target, ret, model, spec, run_name))

    for i, (_, _, target, ret, model, spec, run_name) in enumerate(tasks, start=1):
        run_dir = out_root / run_name
        if run_done(run_dir) and not args.force:
            print(f"[{i}/{len(tasks)}] skip completed {run_name}")
            continue

        cmd = [
            args.python,
            args.pipeline,
            "--run-name",
            run_name,
            "--out-dir",
            str(out_root),
            "--target-col",
            target,
            "--return-col",
            ret,
            "--feature-set",
            args.feature_set,
            "--train-end",
            args.train_end,
            "--val-end",
            args.val_end,
            "--start-date",
            args.start_date,
            "--rebalance-every",
            args.rebalance_every,
            "--transaction-cost-bps",
            args.transaction_cost_bps,
            "--n-jobs",
            args.n_jobs,
            *spec["args"],
        ]
        if args.max_train_rows:
            cmd.extend(["--max-train-rows", args.max_train_rows])
        if args.max_eval_rows:
            cmd.extend(["--max-eval-rows", args.max_eval_rows])

        print(f"[{i}/{len(tasks)}] run {run_name}")
        start = time.time()
        run_dir.mkdir(parents=True, exist_ok=True)
        with (run_dir / "run.log").open("w", encoding="utf-8") as log:
            log.write("$ " + " ".join(cmd) + "\n\n")
            log.flush()
            proc = subprocess.run(cmd, text=True, stdout=log, stderr=subprocess.STDOUT)
        elapsed = time.time() - start
        print(f"[{i}/{len(tasks)}] finished {run_name} rc={proc.returncode} elapsed={elapsed:.1f}s")
        if proc.returncode != 0:
            raise SystemExit(proc.returncode)

        summary = extract_rows(out_root, args.experiment_name)
        summary.to_csv(out_root / f"{args.experiment_name}_all_metrics.csv", index=False)
        best = select_best(summary)
        best.to_csv(out_root / f"{args.experiment_name}_best_metrics.csv", index=False)
        write_report(summary, best, out_root, args.experiment_name)

    summary = extract_rows(out_root, args.experiment_name)
    summary.to_csv(out_root / f"{args.experiment_name}_all_metrics.csv", index=False)
    best = select_best(summary)
    best.to_csv(out_root / f"{args.experiment_name}_best_metrics.csv", index=False)
    write_report(summary, best, out_root, args.experiment_name)
    print(f"Done. Summary: {out_root / f'{args.experiment_name}_all_metrics.csv'}")
    print(f"Done. Report: {out_root / f'{args.experiment_name}_report.md'}")


if __name__ == "__main__":
    main()
