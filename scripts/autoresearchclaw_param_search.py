#!/usr/bin/env python3
"""AutoResearchClaw-style target-specific hyperparameter refinement.

This script consumes the first-pass grid results, generates target-specific
local candidates around each model's validation-best configuration, runs them,
and writes AutoResearchClaw-like stage artifacts for auditability.
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

try:
    from researchclaw.report import generate_report
except Exception:  # pragma: no cover - best effort if ARC import changes
    generate_report = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--pipeline", default="scripts/run_model_pipeline.py")
    parser.add_argument("--base-experiment", default="target_grid_core")
    parser.add_argument("--refine-experiment", default="target_grid_core_refine")
    parser.add_argument("--metrics-dir", default="output/model_pipeline")
    parser.add_argument("--arc-dir", default="output/autoresearchclaw/target_param_search")
    parser.add_argument("--expected-base-runs", type=int, default=84)
    parser.add_argument("--wait-for-base", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--max-wait-seconds", type=int, default=8 * 60 * 60)
    parser.add_argument("--models", nargs="+", default=["lightgbm", "xgboost"], choices=["lightgbm", "xgboost"])
    parser.add_argument("--n-jobs", default="4")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def completed_runs(metrics_dir: Path, experiment_name: str) -> int:
    path = metrics_dir / f"{experiment_name}_all_metrics.csv"
    df = load_csv(path)
    if df.empty:
        return 0
    return int(df["run_name"].nunique())


def wait_for_base(args: argparse.Namespace) -> None:
    if not args.wait_for_base:
        return
    metrics_dir = Path(args.metrics_dir)
    start = time.time()
    while True:
        done = completed_runs(metrics_dir, args.base_experiment)
        print(f"Waiting for base grid: {done}/{args.expected_base_runs} runs complete")
        if done >= args.expected_base_runs:
            return
        if time.time() - start > args.max_wait_seconds:
            raise TimeoutError(
                f"Base experiment did not reach {args.expected_base_runs} runs within budget"
            )
        time.sleep(args.poll_seconds)


def read_config(metrics_dir: Path, run_name: str) -> dict[str, Any]:
    path = metrics_dir / run_name / "config.json"
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(config: dict[str, Any], key: str, default: int) -> int:
    value = config.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(config: dict[str, Any], key: str, default: float) -> float:
    value = config.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, lo: float, hi: float) -> float:
    return min(max(value, lo), hi)


def lightgbm_refinements(config: dict[str, Any]) -> list[dict[str, Any]]:
    n = as_int(config, "n_estimators", 350)
    lr = as_float(config, "learning_rate", 0.04)
    depth = as_int(config, "max_depth", 5)
    leaves = as_int(config, "num_leaves", 31)
    child = as_int(config, "min_child_samples", 250)
    subsample = as_float(config, "subsample", 0.75)
    colsample = as_float(config, "colsample_bytree", 0.75)
    lam = as_float(config, "reg_lambda", 10.0)
    return [
        {
            "tag": "arc_refine_lower_lr",
            "args": [
                "--model", "lightgbm",
                "--n-estimators", str(int(n * 1.5)),
                "--learning-rate", f"{clamp(lr * 0.65, 0.01, 0.08):.4f}",
                "--max-depth", str(depth),
                "--num-leaves", str(leaves),
                "--min-child-samples", str(child),
                "--subsample", f"{subsample:.3f}",
                "--colsample-bytree", f"{colsample:.3f}",
                "--reg-lambda", f"{lam:.3f}",
            ],
        },
        {
            "tag": "arc_refine_more_regularized",
            "args": [
                "--model", "lightgbm",
                "--n-estimators", str(n),
                "--learning-rate", f"{lr:.4f}",
                "--max-depth", str(max(3, depth - 1)),
                "--num-leaves", str(max(7, leaves // 2)),
                "--min-child-samples", str(int(child * 1.5)),
                "--subsample", f"{clamp(subsample - 0.05, 0.55, 0.95):.3f}",
                "--colsample-bytree", f"{clamp(colsample - 0.05, 0.55, 0.95):.3f}",
                "--reg-lambda", f"{lam * 1.7:.3f}",
            ],
        },
        {
            "tag": "arc_refine_more_capacity",
            "args": [
                "--model", "lightgbm",
                "--n-estimators", str(max(200, int(n * 0.85))),
                "--learning-rate", f"{clamp(lr * 1.15, 0.015, 0.08):.4f}",
                "--max-depth", str(min(7, depth + 1)),
                "--num-leaves", str(min(127, max(leaves + 16, int(leaves * 1.6)))),
                "--min-child-samples", str(max(80, int(child * 0.7))),
                "--subsample", f"{clamp(subsample + 0.05, 0.55, 0.95):.3f}",
                "--colsample-bytree", f"{clamp(colsample + 0.05, 0.55, 0.95):.3f}",
                "--reg-lambda", f"{max(1.0, lam * 0.75):.3f}",
            ],
        },
    ]


def xgboost_refinements(config: dict[str, Any]) -> list[dict[str, Any]]:
    n = as_int(config, "n_estimators", 350)
    lr = as_float(config, "learning_rate", 0.04)
    depth = as_int(config, "max_depth", 4)
    child = as_float(config, "min_child_weight", 40.0)
    subsample = as_float(config, "subsample", 0.75)
    colsample = as_float(config, "colsample_bytree", 0.75)
    lam = as_float(config, "reg_lambda", 10.0)
    return [
        {
            "tag": "arc_refine_lower_lr",
            "args": [
                "--model", "xgboost",
                "--n-estimators", str(int(n * 1.5)),
                "--learning-rate", f"{clamp(lr * 0.65, 0.01, 0.08):.4f}",
                "--max-depth", str(depth),
                "--min-child-weight", f"{child:.3f}",
                "--subsample", f"{subsample:.3f}",
                "--colsample-bytree", f"{colsample:.3f}",
                "--reg-lambda", f"{lam:.3f}",
            ],
        },
        {
            "tag": "arc_refine_more_regularized",
            "args": [
                "--model", "xgboost",
                "--n-estimators", str(n),
                "--learning-rate", f"{lr:.4f}",
                "--max-depth", str(max(2, depth - 1)),
                "--min-child-weight", f"{child * 1.7:.3f}",
                "--subsample", f"{clamp(subsample - 0.05, 0.55, 0.95):.3f}",
                "--colsample-bytree", f"{clamp(colsample - 0.05, 0.55, 0.95):.3f}",
                "--reg-lambda", f"{lam * 1.7:.3f}",
            ],
        },
        {
            "tag": "arc_refine_more_capacity",
            "args": [
                "--model", "xgboost",
                "--n-estimators", str(max(200, int(n * 0.85))),
                "--learning-rate", f"{clamp(lr * 1.15, 0.015, 0.08):.4f}",
                "--max-depth", str(min(6, depth + 1)),
                "--min-child-weight", f"{max(10.0, child * 0.65):.3f}",
                "--subsample", f"{clamp(subsample + 0.05, 0.55, 0.95):.3f}",
                "--colsample-bytree", f"{clamp(colsample + 0.05, 0.55, 0.95):.3f}",
                "--reg-lambda", f"{max(1.0, lam * 0.75):.3f}",
            ],
        },
    ]


def refinements_for(model: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    if model == "lightgbm":
        return lightgbm_refinements(config)
    if model == "xgboost":
        return xgboost_refinements(config)
    raise ValueError(model)


def best_rows(metrics_dir: Path, base_experiment: str, models: list[str]) -> pd.DataFrame:
    best_path = metrics_dir / f"{base_experiment}_best_metrics.csv"
    df = load_csv(best_path)
    if df.empty:
        raise FileNotFoundError(best_path)
    rows = df.loc[
        (df["score"] == "model_score") & (df["split"] == "val") & (df["model"].isin(models))
    ].copy()
    if rows.empty:
        raise ValueError("No validation model_score rows found in base best metrics")
    return rows.sort_values(["target_col", "model"])


def run_done(metrics_dir: Path, run_name: str) -> bool:
    run_dir = metrics_dir / run_name
    return (run_dir / "metrics.json").exists() and (run_dir / "config.json").exists()


def run_candidate(args: argparse.Namespace, base_config: dict[str, Any], spec: dict[str, Any], run_name: str) -> int:
    metrics_dir = Path(args.metrics_dir)
    run_dir = metrics_dir / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        args.python,
        args.pipeline,
        "--run-name",
        run_name,
        "--out-dir",
        str(metrics_dir),
        "--target-col",
        str(base_config["target_col"]),
        "--return-col",
        str(base_config["return_col"]),
        "--feature-set",
        str(base_config.get("feature_set", "core")),
        "--train-end",
        str(base_config.get("train_end", "2018-12-31")),
        "--val-end",
        str(base_config.get("val_end", "2020-12-31")),
        "--start-date",
        str(base_config.get("start_date", "2005-01-01")),
        "--rebalance-every",
        str(base_config.get("rebalance_every", 5)),
        "--transaction-cost-bps",
        str(base_config.get("transaction_cost_bps", 5)),
        "--n-jobs",
        str(args.n_jobs),
        *spec["args"],
    ]
    with (run_dir / "run.log").open("w", encoding="utf-8") as log:
        log.write("$ " + " ".join(cmd) + "\n\n")
        log.flush()
        proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, text=True)
    return proc.returncode


def safe_float(v: Any) -> float | None:
    try:
        out = float(v)
    except (TypeError, ValueError):
        return None
    return out if pd.notna(out) else None


def extract_metrics(metrics_dir: Path, experiment_names: list[str]) -> pd.DataFrame:
    rows = []
    for experiment_name in experiment_names:
        for metrics_path in sorted(metrics_dir.glob(f"{experiment_name}__*/metrics.json")):
            run_dir = metrics_path.parent
            config_path = run_dir / "config.json"
            if not config_path.exists():
                continue
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            config = json.loads(config_path.read_text(encoding="utf-8"))
            for score, by_split in metrics.items():
                if not isinstance(by_split, dict):
                    continue
                for split, vals in by_split.items():
                    if not isinstance(vals, dict):
                        continue
                    rows.append(
                        {
                            "run_name": run_dir.name,
                            "experiment": experiment_name,
                            "model": config.get("model_resolved", config.get("model")),
                            "grid_tag": run_dir.name.split("__")[-1],
                            "target_col": config.get("target_col"),
                            "return_col": config.get("return_col"),
                            "score": score,
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
                            "rows": vals.get("rows"),
                            "dates": vals.get("dates"),
                        }
                    )
    return pd.DataFrame(rows)


def select_best(all_metrics: pd.DataFrame) -> pd.DataFrame:
    val = all_metrics.loc[
        (all_metrics["score"] == "model_score") & (all_metrics["split"] == "val")
    ].copy()
    if val.empty:
        return val
    val["rank_key"] = val["rank_ic_ir"].fillna(-1e9)
    idx = val.groupby(["target_col", "model"], dropna=False)["rank_key"].idxmax()
    keys = val.loc[idx, ["run_name"]]
    return all_metrics.merge(keys, on="run_name", how="inner").sort_values(
        ["target_col", "model", "score", "split"]
    )


def write_arc_artifacts(
    arc_dir: Path,
    all_metrics: pd.DataFrame,
    best_metrics: pd.DataFrame,
    base_experiment: str,
    refine_experiment: str,
) -> None:
    stage12 = arc_dir / "stage-12"
    stage13 = arc_dir / "stage-13"
    stage14 = arc_dir / "stage-14"
    for path in [stage12, stage13, stage14]:
        path.mkdir(parents=True, exist_ok=True)

    completed = int(all_metrics["run_name"].nunique()) if not all_metrics.empty else 0
    best_val = best_metrics.loc[
        (best_metrics["score"] == "model_score") & (best_metrics["split"] == "val")
    ].copy()
    iterations = []
    for _, row in best_val.iterrows():
        iterations.append(
            {
                "condition": row["run_name"],
                "target_col": row["target_col"],
                "model": row["model"],
                "best_validation_icir": row["rank_ic_ir"],
                "best_validation_ic": row["mean_rank_ic"],
            }
        )

    experiment_results = {
        "base_experiment": base_experiment,
        "refine_experiment": refine_experiment,
        "runs": completed,
        "best_result": iterations,
    }
    (stage12 / "experiment_results.json").write_text(
        json.dumps(experiment_results, indent=2, allow_nan=False), encoding="utf-8"
    )

    refinement_log = {
        "iterations": iterations,
        "best_metric": max((x["best_validation_icir"] for x in iterations if x["best_validation_icir"] is not None), default=None),
        "metric": "validation rank_ic_ir",
        "selection_rule": "maximize validation rank IC information ratio per target/model",
    }
    (stage13 / "refinement_log.json").write_text(
        json.dumps(refinement_log, indent=2, allow_nan=False), encoding="utf-8"
    )

    condition_summaries = {}
    for _, row in best_val.iterrows():
        condition_summaries[row["run_name"]] = {
            "metrics": {
                "validation_rank_ic": row["mean_rank_ic"],
                "validation_rank_ic_ir": row["rank_ic_ir"],
            },
            "target_col": row["target_col"],
            "model": row["model"],
        }
    experiment_summary = {
        "best_run": {
            "metrics": {
                "primary_metric": refinement_log["best_metric"],
                "total_runs": completed,
            }
        },
        "condition_summaries": condition_summaries,
        "metrics_summary": {},
    }
    (stage14 / "experiment_summary.json").write_text(
        json.dumps(experiment_summary, indent=2, allow_nan=False), encoding="utf-8"
    )

    pipeline_summary = {
        "run_id": arc_dir.name,
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "final_status": "done",
        "stages_done": 3,
        "stages_executed": 3,
    }
    (arc_dir / "pipeline_summary.json").write_text(
        json.dumps(pipeline_summary, indent=2), encoding="utf-8"
    )
    if generate_report is not None:
        try:
            (arc_dir / "researchclaw_report.md").write_text(
                generate_report(arc_dir), encoding="utf-8"
            )
        except Exception as exc:
            (arc_dir / "researchclaw_report_error.txt").write_text(str(exc), encoding="utf-8")


def main() -> None:
    args = parse_args()
    wait_for_base(args)
    metrics_dir = Path(args.metrics_dir)
    arc_dir = Path(args.arc_dir)
    arc_dir.mkdir(parents=True, exist_ok=True)

    rows = best_rows(metrics_dir, args.base_experiment, args.models)
    tasks = []
    for _, row in rows.iterrows():
        base_config = read_config(metrics_dir, str(row["run_name"]))
        for spec in refinements_for(str(row["model"]), base_config):
            run_name = f"{args.refine_experiment}__{row['target_col']}__{row['model']}__{spec['tag']}"
            tasks.append((run_name, base_config, spec))

    for i, (run_name, base_config, spec) in enumerate(tasks, start=1):
        if run_done(metrics_dir, run_name) and not args.force:
            print(f"[{i}/{len(tasks)}] skip completed {run_name}", flush=True)
            continue
        print(f"[{i}/{len(tasks)}] refine {run_name}", flush=True)
        start = time.time()
        rc = run_candidate(args, base_config, spec, run_name)
        elapsed = time.time() - start
        print(f"[{i}/{len(tasks)}] done rc={rc} elapsed={elapsed:.1f}s {run_name}", flush=True)
        if rc != 0:
            raise SystemExit(rc)

        all_metrics = extract_metrics(metrics_dir, [args.base_experiment, args.refine_experiment])
        best_metrics = select_best(all_metrics)
        all_metrics.to_csv(metrics_dir / f"{args.refine_experiment}_all_metrics.csv", index=False)
        best_metrics.to_csv(metrics_dir / f"{args.refine_experiment}_best_metrics.csv", index=False)
        write_arc_artifacts(arc_dir, all_metrics, best_metrics, args.base_experiment, args.refine_experiment)

    all_metrics = extract_metrics(metrics_dir, [args.base_experiment, args.refine_experiment])
    best_metrics = select_best(all_metrics)
    all_metrics.to_csv(metrics_dir / f"{args.refine_experiment}_all_metrics.csv", index=False)
    best_metrics.to_csv(metrics_dir / f"{args.refine_experiment}_best_metrics.csv", index=False)
    write_arc_artifacts(arc_dir, all_metrics, best_metrics, args.base_experiment, args.refine_experiment)
    print(f"Done. Refined metrics: {metrics_dir / f'{args.refine_experiment}_best_metrics.csv'}")
    print(f"Done. AutoResearchClaw artifacts: {arc_dir}")


if __name__ == "__main__":
    main()
