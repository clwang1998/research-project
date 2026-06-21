#!/usr/bin/env python3
"""Run validation-selected model search and rank-ensemble evaluation.

This script is a resumable orchestration layer around ``run_model_pipeline.py``.
It keeps model selection on the validation period, then evaluates a simple
cross-sectional rank ensemble on validation and test predictions from the
selected runs.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_model_pipeline as rmp  # noqa: E402


TARGET_FAMILIES = ["excess_sector", "excess_market"]
HORIZONS = [1, 5, 10]
TREE_MODELS = {"ridge", "lightgbm", "xgboost"}
SUPERVISED_GRAPH_VARIANTS = {
    "supervised_graph": "all",
    "supervised_graph_all": "all",
    "supervised_graph_sector": "sector",
    "supervised_graph_style_knn": "style_knn",
    "supervised_graph_rolling_corr": "rolling_corr",
    "supervised_graph_sector_style": "sector_style",
    "supervised_graph_sector_corr": "sector_corr",
    "supervised_graph_style_corr": "style_corr",
    "supervised_graph_random": "random",
    "supervised_graph_no_edges": "no_edges",
}
GRAPH_SUPERVISED_VARIANTS = {
    "graph_supervised": "all",
    "graph_supervised_all": "all",
    "graph_supervised_sector": "sector",
    "graph_supervised_style_knn": "style_knn",
    "graph_supervised_rolling_corr": "rolling_corr",
    "graph_supervised_sector_style": "sector_style",
    "graph_supervised_sector_corr": "sector_corr",
    "graph_supervised_style_corr": "style_corr",
    "graph_supervised_random": "random",
    "graph_supervised_no_edges": "no_edges",
}
FEATURE_VARIANT_CHOICES = [
    "tabular",
    "fixed_graph",
    *SUPERVISED_GRAPH_VARIANTS.keys(),
    *GRAPH_SUPERVISED_VARIANTS.keys(),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--pipeline", default="scripts/run_model_pipeline.py")
    parser.add_argument("--out-dir", default="output/model_search")
    parser.add_argument("--experiment-name", default="validation_ensemble_search")
    parser.add_argument("--feature-map", default="data/processed/feature_columns_by_group.csv")
    parser.add_argument("--feature-set", choices=["core", "all"], default="all")
    parser.add_argument(
        "--feature-variants",
        nargs="+",
        default=["tabular", "supervised_graph"],
        choices=FEATURE_VARIANT_CHOICES,
    )
    parser.add_argument("--supervised-gat-root", default="data/processed/supervised_graph_embeddings")
    parser.add_argument(
        "--graph-embedding-path",
        default="data/processed/graph_embeddings/graph_relation_embeddings_daily.parquet",
    )
    parser.add_argument("--train-end", default="2018-12-31")
    parser.add_argument("--val-end", default="2021-12-31")
    parser.add_argument("--start-date", default="2001-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--execution-lag-days", default="1")
    parser.add_argument("--embargo-days", default=None)
    parser.add_argument("--rebalance-every", default="auto")
    parser.add_argument("--transaction-cost-bps", default="5")
    parser.add_argument("--min-names-per-date", default="100")
    parser.add_argument("--sector-neutral", action="store_true")
    parser.add_argument("--regime-periods-json", default=None)
    parser.add_argument("--n-jobs", default="-1")
    parser.add_argument("--xgboost-device", default="cpu")
    parser.add_argument("--lightgbm-device-type", default="cpu")
    parser.add_argument("--max-train-rows", default=None)
    parser.add_argument("--max-eval-rows", default=None)
    parser.add_argument("--models", nargs="+", default=["ridge", "lightgbm", "xgboost", "mlp"])
    parser.add_argument("--horizons", nargs="+", type=int, default=HORIZONS)
    parser.add_argument("--families", nargs="+", default=TARGET_FAMILIES)
    parser.add_argument("--ridge-alphas", nargs="+", default=["0.000001", "1", "25", "100"])
    parser.add_argument("--lightgbm-candidates-per-target", type=int, default=0)
    parser.add_argument("--xgboost-candidates-per-target", type=int, default=0)
    parser.add_argument(
        "--tree-seeds",
        nargs="+",
        type=int,
        default=[42],
        help="Seeds used to expand LightGBM/XGBoost specs for seed-bagging ensembles.",
    )
    parser.add_argument("--mlp-hidden-sizes", nargs="+", type=int, default=[16, 32, 64])
    parser.add_argument("--mlp-num-layers", nargs="+", type=int, default=[1, 2])
    parser.add_argument("--mlp-learning-rates", nargs="+", default=["0.0001", "0.0003", "0.001"])
    parser.add_argument("--mlp-dropouts", nargs="+", default=["0.1", "0.3", "0.5"])
    parser.add_argument("--mlp-window-sizes", nargs="+", type=int, default=[20, 60])
    parser.add_argument("--mlp-weight-decays", nargs="+", default=["0.0001", "0.001"])
    parser.add_argument("--mlp-candidates-per-target", type=int, default=8)
    parser.add_argument("--mlp-epochs", default="30")
    parser.add_argument("--mlp-batch-size", default="8192")
    parser.add_argument("--mlp-patience", default="5")
    parser.add_argument("--selection-metric", default="rank_ic_ir", choices=["rank_ic_ir", "mean_rank_ic", "ic_ir", "mean_ic"])
    parser.add_argument(
        "--stability-min-years",
        type=int,
        default=2,
        help="Minimum validation calendar years required for stability-filtered ensembles.",
    )
    parser.add_argument(
        "--stability-min-positive-year-frac",
        type=float,
        default=0.67,
        help="Minimum fraction of validation years with yearly rank IC above --stability-min-year-rank-ic.",
    )
    parser.add_argument(
        "--stability-min-year-rank-ic",
        type=float,
        default=0.0,
        help="Minimum yearly mean rank IC counted as positive for stability filtering.",
    )
    parser.add_argument(
        "--stability-min-regime-rank-ic",
        type=float,
        default=0.0,
        help="Minimum available validation-regime rank IC for stability filtering.",
    )
    parser.add_argument(
        "--stability-min-val-rank-ic",
        type=float,
        default=0.0,
        help="Minimum full-validation rank IC for stability filtering.",
    )
    parser.add_argument(
        "--mlp-ensemble-policy",
        choices=["include", "stable_only", "exclude"],
        default="stable_only",
        help="Whether validation-selected MLP members can enter the gated ensemble.",
    )
    parser.add_argument(
        "--mlp-min-ensemble-val-rank-ic",
        type=float,
        default=0.0,
        help="Minimum full-validation rank IC for an MLP member in the gated ensemble.",
    )
    parser.add_argument(
        "--save-ensemble-predictions",
        action="store_true",
        help="Persist full ensemble prediction parquet files; metrics are written either way.",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-runs", action="store_true", help="Only rebuild aggregation and ensembles.")
    parser.add_argument(
        "--subprocess",
        action="store_true",
        help="Run each candidate as a separate run_model_pipeline.py subprocess.",
    )
    return parser.parse_args()


def target_name(family: str, horizon: int) -> str:
    return f"target_{family}_fwd_{horizon}d"


def return_name(horizon: int) -> str:
    return f"target_ret_fwd_{horizon}d"


def safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if pd.notna(out) and math.isfinite(out) else None


def clean_json(value: Any) -> Any:
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


def run_done(run_dir: Path) -> bool:
    return (run_dir / "metrics.json").exists() and (run_dir / "config.json").exists()


def supervised_embedding_for(root: Path, target_col: str, relation_ablation: str | None = None) -> Path | None:
    candidates = []
    for config_path in root.glob("*/config.json"):
        run_dir = config_path.parent
        emb_path = run_dir / "supervised_gat_oof_embeddings.parquet"
        if not emb_path.exists():
            continue
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        config_ablation = config.get("relation_ablation", "all")
        if config.get("target_col") == target_col and (
            relation_ablation is None or config_ablation == relation_ablation
        ):
            candidates.append((emb_path.stat().st_mtime, emb_path))
    if not candidates:
        return None
    return sorted(candidates)[-1][1]


def lightgbm_specs() -> list[dict[str, Any]]:
    return [
        {
            "tag": "lgbm_balanced",
            "args": [
                "--model", "lightgbm", "--n-estimators", "350", "--learning-rate", "0.04",
                "--max-depth", "5", "--num-leaves", "31", "--min-child-samples", "250",
                "--subsample", "0.75", "--colsample-bytree", "0.75", "--reg-lambda", "10",
            ],
        },
        {
            "tag": "lgbm_shallow_regularized",
            "args": [
                "--model", "lightgbm", "--n-estimators", "550", "--learning-rate", "0.025",
                "--max-depth", "4", "--num-leaves", "15", "--min-child-samples", "400",
                "--subsample", "0.8", "--colsample-bytree", "0.7", "--reg-lambda", "20",
            ],
        },
        {
            "tag": "lgbm_deeper",
            "args": [
                "--model", "lightgbm", "--n-estimators", "300", "--learning-rate", "0.05",
                "--max-depth", "6", "--num-leaves", "63", "--min-child-samples", "180",
                "--subsample", "0.75", "--colsample-bytree", "0.85", "--reg-lambda", "8",
            ],
        },
        {
            "tag": "lgbm_low_lr_large",
            "args": [
                "--model", "lightgbm", "--n-estimators", "800", "--learning-rate", "0.015",
                "--max-depth", "5", "--num-leaves", "31", "--min-child-samples", "300",
                "--subsample", "0.7", "--colsample-bytree", "0.7", "--reg-lambda", "30",
            ],
        },
    ]


def xgboost_specs() -> list[dict[str, Any]]:
    return [
        {
            "tag": "xgb_balanced",
            "args": [
                "--model", "xgboost", "--n-estimators", "350", "--learning-rate", "0.04",
                "--max-depth", "4", "--min-child-weight", "40", "--subsample", "0.75",
                "--colsample-bytree", "0.75", "--reg-lambda", "10",
            ],
        },
        {
            "tag": "xgb_shallow_regularized",
            "args": [
                "--model", "xgboost", "--n-estimators", "550", "--learning-rate", "0.025",
                "--max-depth", "3", "--min-child-weight", "80", "--subsample", "0.8",
                "--colsample-bytree", "0.7", "--reg-lambda", "20",
            ],
        },
        {
            "tag": "xgb_deeper",
            "args": [
                "--model", "xgboost", "--n-estimators", "300", "--learning-rate", "0.05",
                "--max-depth", "5", "--min-child-weight", "30", "--subsample", "0.75",
                "--colsample-bytree", "0.85", "--reg-lambda", "8",
            ],
        },
        {
            "tag": "xgb_low_lr_large",
            "args": [
                "--model", "xgboost", "--n-estimators", "800", "--learning-rate", "0.015",
                "--max-depth", "4", "--min-child-weight", "60", "--subsample", "0.7",
                "--colsample-bytree", "0.7", "--reg-lambda", "30",
            ],
        },
    ]


def ridge_specs(args: argparse.Namespace) -> list[dict[str, Any]]:
    specs = []
    for alpha in args.ridge_alphas:
        tag = "linear_alpha_" + str(alpha).replace(".", "p")
        specs.append({"tag": tag, "args": ["--model", "ridge", "--ridge-alpha", str(alpha)]})
    return specs


def mlp_specs(args: argparse.Namespace) -> list[dict[str, Any]]:
    combos = list(
        itertools.product(
            args.mlp_hidden_sizes,
            args.mlp_num_layers,
            args.mlp_learning_rates,
            args.mlp_dropouts,
            args.mlp_window_sizes,
            args.mlp_weight_decays,
        )
    )
    if args.mlp_candidates_per_target > 0 and len(combos) > args.mlp_candidates_per_target:
        idx = np.linspace(0, len(combos) - 1, args.mlp_candidates_per_target, dtype=int)
        combos = [combos[int(i)] for i in idx]
    specs = []
    for hidden_size, num_layers, lr, dropout, window, weight_decay in combos:
        hidden = ",".join([str(hidden_size)] * int(num_layers))
        tag = f"mlp_h{hidden_size}_l{num_layers}_lr{lr}_do{dropout}_w{window}_wd{weight_decay}"
        tag = tag.replace(".", "p")
        specs.append(
            {
                "tag": tag,
                "args": [
                    "--model", "mlp",
                    "--mlp-hidden", hidden,
                    "--mlp-lr", str(lr),
                    "--mlp-dropout", str(dropout),
                    "--mlp-epochs", str(args.mlp_epochs),
                    "--mlp-batch-size", str(args.mlp_batch_size),
                    "--mlp-patience", str(args.mlp_patience),
                    "--mlp-weight-decay", str(weight_decay),
                    "--max-lookback-days", str(window),
                ],
            }
        )
    return specs


def specs_for_model(model: str, args: argparse.Namespace) -> list[dict[str, Any]]:
    if model == "ridge":
        return ridge_specs(args)
    if model == "lightgbm":
        specs = lightgbm_specs()
        specs = specs[: args.lightgbm_candidates_per_target] if args.lightgbm_candidates_per_target > 0 else specs
        return expand_tree_seed_specs(specs, args.tree_seeds)
    if model == "xgboost":
        specs = xgboost_specs()
        specs = specs[: args.xgboost_candidates_per_target] if args.xgboost_candidates_per_target > 0 else specs
        return expand_tree_seed_specs(specs, args.tree_seeds)
    if model == "mlp":
        return mlp_specs(args)
    raise ValueError(model)


def expand_tree_seed_specs(specs: list[dict[str, Any]], seeds: list[int]) -> list[dict[str, Any]]:
    out = []
    unique_seeds = list(dict.fromkeys(int(seed) for seed in seeds))
    for spec in specs:
        for seed in unique_seeds:
            args_with_seed = [*spec["args"], "--sample-seed", str(seed)]
            tag = spec["tag"] if len(unique_seeds) == 1 and seed == 42 else f"{spec['tag']}_seed{seed}"
            out.append({"tag": tag, "args": args_with_seed})
    return out


def variant_args(
    variant: str,
    target_col: str,
    args: argparse.Namespace,
) -> tuple[str, list[str]] | None:
    if variant == "tabular":
        return "tabular", []
    if variant == "fixed_graph":
        path = Path(args.graph_embedding_path)
        if not path.exists():
            return None
        return "fixed_graph", ["--include-graph-embeddings", "--graph-embedding-path", str(path)]

    if variant in SUPERVISED_GRAPH_VARIANTS:
        ablation = SUPERVISED_GRAPH_VARIANTS[variant]
        supervised_path = supervised_embedding_for(Path(args.supervised_gat_root), target_col, ablation)
        if supervised_path is None:
            return None
        return (
            variant,
            ["--include-supervised-graph-embeddings", "--supervised-graph-embedding-path", str(supervised_path)],
        )

    if variant in GRAPH_SUPERVISED_VARIANTS:
        ablation = GRAPH_SUPERVISED_VARIANTS[variant]
        supervised_path = supervised_embedding_for(Path(args.supervised_gat_root), target_col, ablation)
        if supervised_path is None:
            return None
        path = Path(args.graph_embedding_path)
        if not path.exists():
            return None
        return (
            variant,
            [
                "--include-graph-embeddings", "--graph-embedding-path", str(path),
                "--include-supervised-graph-embeddings", "--supervised-graph-embedding-path", str(supervised_path),
            ],
        )
    raise ValueError(variant)


def build_tasks(args: argparse.Namespace) -> list[dict[str, Any]]:
    tasks = []
    for horizon in args.horizons:
        for family in args.families:
            target = target_name(family, horizon)
            ret = return_name(horizon)
            for variant in args.feature_variants:
                v = variant_args(variant, target, args)
                if v is None:
                    print(f"Skip variant={variant} target={target}: required embedding file not found.")
                    continue
                variant_tag, variant_extra = v
                for model in args.models:
                    for spec in specs_for_model(model, args):
                        run_name = "__".join(
                            [
                                args.experiment_name,
                                target,
                                variant_tag,
                                model,
                                spec["tag"],
                            ]
                        )
                        tasks.append(
                            {
                                "horizon": horizon,
                                "family": family,
                                "target": target,
                                "return": ret,
                                "variant": variant_tag,
                                "model": model,
                                "spec": spec,
                                "run_name": run_name,
                                "variant_extra": variant_extra,
                            }
                        )
    return tasks


def run_candidate(task: dict[str, Any], args: argparse.Namespace, out_root: Path) -> int:
    run_dir = out_root / task["run_name"]
    cmd = [
        args.python,
        args.pipeline,
        "--run-name", task["run_name"],
        "--out-dir", str(out_root),
        "--feature-map", args.feature_map,
        "--target-col", task["target"],
        "--return-col", task["return"],
        "--feature-set", args.feature_set,
        "--train-end", args.train_end,
        "--val-end", args.val_end,
        "--start-date", args.start_date,
        "--execution-lag-days", args.execution_lag_days,
        "--transaction-cost-bps", args.transaction_cost_bps,
        "--min-names-per-date", args.min_names_per_date,
        "--n-jobs", args.n_jobs,
        "--xgboost-device", args.xgboost_device,
        "--lightgbm-device-type", args.lightgbm_device_type,
        "--save-predictions",
        *task["variant_extra"],
        *task["spec"]["args"],
    ]
    if args.end_date:
        cmd.extend(["--end-date", args.end_date])
    if args.rebalance_every and str(args.rebalance_every) != "auto":
        cmd.extend(["--rebalance-every", str(args.rebalance_every)])
    if args.max_train_rows:
        cmd.extend(["--max-train-rows", args.max_train_rows])
    if args.max_eval_rows:
        cmd.extend(["--max-eval-rows", args.max_eval_rows])
    if args.embargo_days is not None:
        cmd.extend(["--embargo-days", args.embargo_days])
    if args.sector_neutral:
        cmd.append("--sector-neutral")
    if args.regime_periods_json:
        cmd.extend(["--regime-periods-json", args.regime_periods_json])

    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "run.log").open("w", encoding="utf-8") as log:
        log.write("$ " + " ".join(cmd) + "\n\n")
        log.flush()
        proc = subprocess.run(cmd, text=True, stdout=log, stderr=subprocess.STDOUT)
    return proc.returncode


def pipeline_args_for(task: dict[str, Any], args: argparse.Namespace) -> argparse.Namespace:
    saved = sys.argv
    try:
        sys.argv = [
            "run_model_pipeline",
            "--run-name", task["run_name"],
            "--out-dir", str(Path(args.out_dir)),
            "--feature-map", args.feature_map,
            "--target-col", task["target"],
            "--return-col", task["return"],
            "--feature-set", args.feature_set,
            "--train-end", args.train_end,
            "--val-end", args.val_end,
            "--start-date", args.start_date,
            "--execution-lag-days", str(args.execution_lag_days),
            "--transaction-cost-bps", str(args.transaction_cost_bps),
            "--min-names-per-date", str(args.min_names_per_date),
            "--n-jobs", str(args.n_jobs),
            "--xgboost-device", str(args.xgboost_device),
            "--lightgbm-device-type", str(args.lightgbm_device_type),
            *task["variant_extra"],
            *task["spec"]["args"],
        ]
        if args.end_date:
            sys.argv.extend(["--end-date", args.end_date])
        if args.rebalance_every and str(args.rebalance_every) != "auto":
            sys.argv.extend(["--rebalance-every", str(args.rebalance_every)])
        if args.max_train_rows:
            sys.argv.extend(["--max-train-rows", str(args.max_train_rows)])
        if args.max_eval_rows:
            sys.argv.extend(["--max-eval-rows", str(args.max_eval_rows)])
        if args.embargo_days is not None:
            sys.argv.extend(["--embargo-days", str(args.embargo_days)])
        if args.sector_neutral:
            sys.argv.append("--sector-neutral")
        if args.regime_periods_json:
            sys.argv.extend(["--regime-periods-json", args.regime_periods_json])
        return rmp.parse_args()
    finally:
        sys.argv = saved


def run_group_in_process(
    group_tasks: list[dict[str, Any]],
    args: argparse.Namespace,
    out_root: Path,
) -> None:
    if not args.force:
        completed = [task for task in group_tasks if run_done(out_root / task["run_name"])]
        if len(completed) == len(group_tasks):
            for task in group_tasks:
                print(f"skip completed {task['run_name']}", flush=True)
            return

    first_args = pipeline_args_for(group_tasks[0], args)
    fmap = rmp.read_feature_map(first_args.feature_map)
    feature_cols = rmp.select_feature_columns(first_args, fmap)
    if first_args.include_graph_embeddings:
        feature_cols = list(dict.fromkeys(feature_cols + rmp.GRAPH_FEATURES))
    if first_args.include_supervised_graph_embeddings:
        feature_cols = list(dict.fromkeys(feature_cols + rmp.SUPERVISED_GRAPH_FEATURES))
    graph_feature_cols = [c for c in feature_cols if c in rmp.GRAPH_FEATURES]
    supervised_graph_feature_cols = [c for c in feature_cols if c in rmp.SUPERVISED_GRAPH_FEATURES]
    feature_variant = str(group_tasks[0]["variant"])
    first_args.feature_variant_label = feature_variant

    panel = rmp.load_panel(first_args, feature_cols, fmap)
    horizon_days = rmp.infer_horizon_days(first_args.target_col, first_args.return_col)
    embargo_days = rmp.resolve_embargo_days(horizon_days, first_args.embargo_days)
    first_args.label_horizon_days = horizon_days
    first_args.embargo_days_resolved = embargo_days
    if first_args.rebalance_every is None:
        first_args.rebalance_every = horizon_days
    panel = rmp.attach_effective_labels(
        panel,
        first_args.target_col,
        first_args.return_col,
        horizon_days,
        first_args.execution_lag_days,
    )
    panel = rmp.apply_liquidity_universe(panel, "log_dollar_volume", first_args.min_dollar_volume_pct)
    panel = rmp.winsorize_by_date(panel, feature_cols, first_args.winsorize_pct)
    raw_masks = rmp.split_masks(panel, first_args.train_end, first_args.val_end)
    masks = rmp.apply_purge_embargo(
        panel,
        raw_masks,
        first_args.train_end,
        first_args.val_end,
        embargo_days,
    )
    audit = rmp.split_audit(panel, raw_masks, masks)
    train_fit_mask = rmp.sample_mask(
        panel, masks["train"], first_args.max_train_rows, first_args.sample_seed
    )
    prep = rmp.fit_preprocessor(panel, feature_cols, train_fit_mask)
    x_train = prep.transform(panel.loc[train_fit_mask])
    y_train = panel.loc[train_fit_mask, rmp.EVAL_TARGET_COL].to_numpy(dtype=np.float32)
    baseline_feature = (
        "cs_rank_mom_252d_skip_21d"
        if "cs_rank_mom_252d_skip_21d" in panel.columns
        else feature_cols[0]
    )
    eval_masks = {
        split: rmp.limit_eval_mask_by_date(panel, masks[split], first_args.max_eval_rows)
        for split in ["val", "test"]
    }
    base_eval_frames = {
        split: panel.loc[eval_masks[split]].copy()
        for split in ["val", "test"]
        if eval_masks[split].any()
    }
    for frame in base_eval_frames.values():
        frame["baseline_score"] = frame[baseline_feature].astype("float32")

    for task in group_tasks:
        run_dir = out_root / task["run_name"]
        if run_done(run_dir) and not args.force:
            print(f"skip completed {task['run_name']}", flush=True)
            continue
        run_dir.mkdir(parents=True, exist_ok=True)
        task_args = pipeline_args_for(task, args)
        task_args.label_horizon_days = horizon_days
        task_args.embargo_days_resolved = embargo_days
        if task_args.rebalance_every is None:
            task_args.rebalance_every = horizon_days
        task_args.feature_variant_label = feature_variant
        start = time.time()
        with (run_dir / "run.log").open("w", encoding="utf-8") as log:
            log.write(
                "in-process candidate "
                + json.dumps(
                    {
                        "run_name": task["run_name"],
                        "target": task["target"],
                        "variant": task["variant"],
                        "model": task["model"],
                        "tag": task["spec"]["tag"],
                    }
                )
                + "\n"
            )
        model_name, model = rmp.fit_model(task_args, x_train, y_train)
        metrics: dict[str, dict[str, object]] = {"baseline_score": {}, "model_score": {}}
        regime_metrics: dict[str, dict[str, dict[str, object]]] = {
            "baseline_score": {},
            "model_score": {},
        }
        pred_frames = []
        for split, frame in base_eval_frames.items():
            split_df = frame.copy()
            x_eval = prep.transform(split_df)
            split_df["model_score"] = model.predict(x_eval)
            del x_eval
            for score_col in ["baseline_score", "model_score"]:
                metrics[score_col][split] = rmp.evaluate_scores(
                    split_df,
                    score_col,
                    rmp.EVAL_TARGET_COL,
                    rmp.EVAL_RETURN_COL,
                    task_args,
                    split,
                    run_dir,
                )
                regime_metrics[score_col][split] = rmp.evaluate_regimes(
                    split_df,
                    score_col,
                    rmp.EVAL_TARGET_COL,
                    rmp.EVAL_RETURN_COL,
                    task_args,
                    run_dir,
                    split,
                )
            pred_frames.append(split_df)

        feature_importance = pd.DataFrame({"feature": feature_cols})
        if isinstance(model, rmp.NumpyRidgeRegressor):
            feature_importance["importance"] = np.abs(model.coef_)
            feature_importance["coefficient"] = model.coef_
        elif hasattr(model, "feature_importances_"):
            feature_importance["importance"] = getattr(model, "feature_importances_")
        else:
            feature_importance["importance"] = np.nan
        feature_importance.sort_values("importance", ascending=False).to_csv(
            run_dir / "feature_importance.csv", index=False
        )

        if pred_frames:
            pred_panel = pd.concat(pred_frames, ignore_index=True)
            pred_cols = rmp.KEY_COLS + rmp.META_COLS + [
                task_args.target_col,
                task_args.return_col,
                rmp.EVAL_TARGET_COL,
                rmp.EVAL_RETURN_COL,
                rmp.LABEL_END_DATE_COL,
                "baseline_score",
                "model_score",
            ]
            pred_panel.loc[:, pred_cols].to_parquet(
                run_dir / "predictions_val_test.parquet", index=False
            )

        config = vars(task_args).copy()
        config["run_name"] = task["run_name"]
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
        (run_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
        pd.DataFrame({"feature": feature_cols}).to_csv(run_dir / "selected_features.csv", index=False)
        (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        (run_dir / "regime_metrics.json").write_text(
            json.dumps(rmp.clean_json(regime_metrics), indent=2, allow_nan=False),
            encoding="utf-8",
        )
        rmp.write_summary_markdown(
            run_dir / "summary.md",
            task_args,
            model_name,
            feature_cols,
            metrics,
            audit,
        )
        elapsed = time.time() - start
        print(f"completed {task['run_name']} model={model_name} elapsed={elapsed:.1f}s", flush=True)

    del x_train, y_train, panel


def group_key_for_task(task: dict[str, Any], args: argparse.Namespace) -> tuple[Any, ...]:
    task_args = pipeline_args_for(task, args)
    return (
        task["target"],
        task["return"],
        task["variant"],
        task_args.include_graph_embeddings,
        task_args.graph_embedding_path,
        task_args.include_supervised_graph_embeddings,
        task_args.supervised_graph_embedding_path,
        task_args.max_lookback_days,
    )


def run_tasks_in_process(tasks: list[dict[str, Any]], args: argparse.Namespace, out_root: Path) -> None:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for task in tasks:
        groups.setdefault(group_key_for_task(task, args), []).append(task)
    for i, group_tasks in enumerate(groups.values(), start=1):
        key = group_key_for_task(group_tasks[0], args)
        print(
            f"[group {i}/{len(groups)}] target={group_tasks[0]['target']} "
            f"variant={group_tasks[0]['variant']} max_lookback={key[-1]} "
            f"candidates={len(group_tasks)}",
            flush=True,
        )
        run_group_in_process(group_tasks, args, out_root)
        summary = extract_rows(out_root, args.experiment_name)
        summary.to_csv(out_root / f"{args.experiment_name}_all_metrics.csv", index=False)
        best = select_best(summary, args.selection_metric)
        best.to_csv(out_root / f"{args.experiment_name}_best_metrics.csv", index=False)


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
                target = config.get("target_col")
                rows.append(
                    {
                        "run_name": run_dir.name,
                        "model": config.get("model_resolved", config.get("model")),
                        "model_requested": config.get("model"),
                        "feature_variant": config.get("feature_variant"),
                        "grid_tag": run_dir.name.split("__")[-1],
                        "target_col": target,
                        "return_col": config.get("return_col"),
                        "score": score_name,
                        "split": split,
                        "mean_rank_ic": safe_float(vals.get("mean_rank_ic")),
                        "mean_ic": safe_float(vals.get("mean_ic")),
                        "rank_ic_ir": safe_float(vals.get("rank_ic_ir")),
                        "ic_ir": safe_float(vals.get("ic_ir")),
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


def select_best(summary: pd.DataFrame, metric: str) -> pd.DataFrame:
    if summary.empty:
        return summary
    val = summary.loc[(summary["score"] == "model_score") & (summary["split"] == "val")].copy()
    if val.empty:
        return val
    val["_rank_key"] = pd.to_numeric(val[metric], errors="coerce").fillna(-1e9)
    idx = val.groupby(["target_col", "model", "feature_variant"], dropna=False)["_rank_key"].idxmax()
    selected = val.loc[idx, ["run_name"]].drop_duplicates()
    return summary.merge(selected, on="run_name", how="inner").sort_values(
        ["target_col", "model", "feature_variant", "score", "split"]
    )


def build_eval_args(config: dict[str, Any], args: argparse.Namespace) -> SimpleNamespace:
    horizon = rmp.infer_horizon_days(config["target_col"], config["return_col"])
    rebalance_every = config.get("rebalance_every") or horizon
    return SimpleNamespace(
        rebalance_every=int(rebalance_every),
        long_short_pct=float(config.get("long_short_pct", 0.10)),
        transaction_cost_bps=float(config.get("transaction_cost_bps", args.transaction_cost_bps)),
        min_names_per_date=int(config.get("min_names_per_date", args.min_names_per_date)),
        sector_neutral=bool(config.get("sector_neutral", False)),
        regime_periods_json=config.get("regime_periods_json"),
        label_horizon_days=horizon,
    )


def rank_pct_by_date(df: pd.DataFrame, col: str) -> pd.Series:
    return df.groupby("date", observed=True)[col].rank(pct=True, method="average")


def mlp_gated_selection(
    selected: pd.DataFrame,
    stability_by_run: dict[str, dict[str, Any]],
    args: argparse.Namespace,
) -> pd.DataFrame:
    if args.mlp_ensemble_policy == "include":
        return selected.copy()
    if args.mlp_ensemble_policy == "exclude":
        return selected.loc[selected["model"] != "mlp"].copy()

    rows = []
    for _, row in selected.iterrows():
        if row["model"] != "mlp":
            rows.append(row)
            continue
        stability = stability_by_run.get(str(row["run_name"]), {})
        val_rank_ic = safe_float(row.get("mean_rank_ic"))
        selection_value = safe_float(row.get(args.selection_metric))
        if (
            stability.get("stable") is True
            and val_rank_ic is not None
            and val_rank_ic >= args.mlp_min_ensemble_val_rank_ic
            and selection_value is not None
            and selection_value > 0
        ):
            rows.append(row)
    return pd.DataFrame(rows) if rows else selected.iloc[0:0].copy()


def candidate_stability(row: pd.Series, out_root: Path, args: argparse.Namespace) -> dict[str, Any]:
    run_dir = out_root / str(row["run_name"])
    out: dict[str, Any] = {
        "stable": False,
        "stability_reason": "",
        "val_years": 0,
        "val_positive_year_frac": math.nan,
        "val_min_year_rank_ic": math.nan,
        "val_min_regime_rank_ic": math.nan,
    }
    val_rank_ic = safe_float(row.get("mean_rank_ic"))
    if val_rank_ic is None or val_rank_ic < args.stability_min_val_rank_ic:
        out["stability_reason"] = "low_full_val_rank_ic"
        return out

    ic_path = run_dir / "model_score_val_rank_ic.csv"
    if not ic_path.exists():
        out["stability_reason"] = "missing_val_rank_ic_file"
        return out
    ic = pd.read_csv(ic_path)
    if ic.empty or "date" not in ic.columns or "rank_ic" not in ic.columns:
        out["stability_reason"] = "empty_val_rank_ic_file"
        return out
    dates = pd.to_datetime(ic["date"], errors="coerce")
    yearly = ic.assign(year=dates.dt.year).groupby("year", observed=True)["rank_ic"].mean().dropna()
    out["val_years"] = int(len(yearly))
    if len(yearly) < args.stability_min_years:
        out["stability_reason"] = "too_few_val_years"
        return out
    positive_frac = float((yearly >= args.stability_min_year_rank_ic).mean())
    min_year = float(yearly.min())
    out["val_positive_year_frac"] = positive_frac
    out["val_min_year_rank_ic"] = min_year
    if positive_frac < args.stability_min_positive_year_frac:
        out["stability_reason"] = "unstable_yearly_rank_ic"
        return out

    regime_path = run_dir / "model_score_val_regime_metrics.csv"
    if regime_path.exists():
        regimes = pd.read_csv(regime_path)
        if not regimes.empty and "mean_rank_ic" in regimes.columns:
            regime_vals = pd.to_numeric(regimes["mean_rank_ic"], errors="coerce").dropna()
            if not regime_vals.empty:
                min_regime = float(regime_vals.min())
                out["val_min_regime_rank_ic"] = min_regime
                if min_regime < args.stability_min_regime_rank_ic:
                    out["stability_reason"] = "unstable_regime_rank_ic"
                    return out

    out["stable"] = True
    out["stability_reason"] = "pass"
    return out


def ensemble_definitions(selected: pd.DataFrame, out_root: Path, args: argparse.Namespace) -> list[dict[str, Any]]:
    stable_rows = []
    stability_by_run: dict[str, dict[str, Any]] = {}
    for _, row in selected.iterrows():
        stability = candidate_stability(row, out_root, args)
        stability_by_run[str(row["run_name"])] = stability
        if stability["stable"]:
            stable_rows.append(row)
    stable = pd.DataFrame(stable_rows) if stable_rows else selected.iloc[0:0].copy()
    mlp_gated = mlp_gated_selection(selected, stability_by_run, args)
    supervised_all_variants = {"supervised_graph", "supervised_graph_all"}
    supervised_any_variants = set(SUPERVISED_GRAPH_VARIANTS)
    return [
        {
            "name": "ensemble_all_val_selected",
            "description": "Validation-selected best run per target/model/feature variant.",
            "rows": selected,
            "stability": stability_by_run,
        },
        {
            "name": "ensemble_mlp_gated",
            "description": "Validation-selected members, with MLP included only if it passes validation stability gates.",
            "rows": mlp_gated,
            "stability": stability_by_run,
        },
        {
            "name": "ensemble_no_mlp",
            "description": "Validation-selected members excluding all MLP runs.",
            "rows": selected.loc[selected["model"] != "mlp"].copy(),
            "stability": stability_by_run,
        },
        {
            "name": "ensemble_tree_only",
            "description": "Validation-selected Ridge, LightGBM, and XGBoost members only.",
            "rows": selected.loc[selected["model"].isin(TREE_MODELS)].copy(),
            "stability": stability_by_run,
        },
        {
            "name": "ensemble_supervised_graph_tree",
            "description": "Validation-selected all-relation supervised_graph members from Ridge, LightGBM, and XGBoost.",
            "rows": selected.loc[
                selected["model"].isin(TREE_MODELS) & selected["feature_variant"].isin(supervised_all_variants)
            ].copy(),
            "stability": stability_by_run,
        },
        {
            "name": "ensemble_graph_ablation_tree",
            "description": "Validation-selected supervised graph ablation members from Ridge, LightGBM, and XGBoost.",
            "rows": selected.loc[
                selected["model"].isin(TREE_MODELS) & selected["feature_variant"].isin(supervised_any_variants)
            ].copy(),
            "stability": stability_by_run,
        },
        {
            "name": "ensemble_stability_filtered",
            "description": "Validation-selected members that pass yearly and available regime stability filters.",
            "rows": stable,
            "stability": stability_by_run,
        },
    ]


def evaluate_single_ensemble(
    selected: pd.DataFrame,
    out_root: Path,
    target_col: str,
    ensemble_name: str,
    ensemble_description: str,
    stability_by_run: dict[str, dict[str, Any]],
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected = selected.sort_values(args.selection_metric, ascending=False)
    if len(selected) < 2:
        return [], []
    pred_frames = []
    weights = []
    configs = []
    for _, row in selected.iterrows():
        run_dir = out_root / str(row["run_name"])
        pred_path = run_dir / "predictions_val_test.parquet"
        config_path = run_dir / "config.json"
        if not pred_path.exists() or not config_path.exists():
            continue
        config = json.loads(config_path.read_text(encoding="utf-8"))
        score_name = f"score__{row['model']}__{row['feature_variant']}__{row['grid_tag']}"
        cols = ["date", "symbol", "sector", rmp.EVAL_TARGET_COL, rmp.EVAL_RETURN_COL, "model_score"]
        pred = pd.read_parquet(pred_path, columns=cols).rename(columns={"model_score": score_name})
        pred_frames.append(pred)
        weight = max(0.0, float(row.get(args.selection_metric) or 0.0))
        weights.append(weight)
        stability = stability_by_run.get(str(row["run_name"]), {})
        configs.append(
            {
                "run_name": row["run_name"],
                "model": row["model"],
                "feature_variant": row["feature_variant"],
                "grid_tag": row["grid_tag"],
                "score_col": score_name,
                "weight": weight,
                "stable": stability.get("stable"),
                "stability_reason": stability.get("stability_reason"),
                "val_positive_year_frac": stability.get("val_positive_year_frac"),
                "val_min_year_rank_ic": stability.get("val_min_year_rank_ic"),
                "val_min_regime_rank_ic": stability.get("val_min_regime_rank_ic"),
            }
        )
    if len(pred_frames) < 2:
        return [], []

    merged = pred_frames[0]
    score_cols = [configs[0]["score_col"]]
    for pred, cfg in zip(pred_frames[1:], configs[1:]):
        merged = merged.merge(
            pred.drop(columns=["sector", rmp.EVAL_TARGET_COL, rmp.EVAL_RETURN_COL]),
            on=["date", "symbol"],
            how="inner",
        )
        score_cols.append(cfg["score_col"])
    for col in score_cols:
        merged[f"rank__{col}"] = rank_pct_by_date(merged, col)
    rank_cols = [f"rank__{col}" for col in score_cols]

    score_equal = f"{ensemble_name}_rank_equal"
    score_weighted = f"{ensemble_name}_rank_weighted"
    merged[score_equal] = merged[rank_cols].mean(axis=1)
    weight_arr = np.asarray(weights[: len(rank_cols)], dtype=np.float64)
    if np.isfinite(weight_arr).all() and weight_arr.sum() > 0:
        weight_arr = weight_arr / weight_arr.sum()
        merged[score_weighted] = (merged[rank_cols].to_numpy() * weight_arr).sum(axis=1)
    else:
        merged[score_weighted] = merged[score_equal]

    config0 = json.loads((out_root / str(selected.iloc[0]["run_name"]) / "config.json").read_text(encoding="utf-8"))
    eval_args = build_eval_args(config0, args)
    dates = pd.to_datetime(merged["date"])
    val_end = pd.Timestamp(args.val_end)
    split_masks = {"val": dates <= val_end, "test": dates > val_end}
    target_dir = out_root / f"{args.experiment_name}_ensembles" / target_col / ensemble_name
    target_dir.mkdir(parents=True, exist_ok=True)
    if args.save_ensemble_predictions:
        merged.to_parquet(target_dir / "ensemble_predictions.parquet", index=False)
    (target_dir / "ensemble_members.json").write_text(
        json.dumps(
            clean_json(
                {
                    "ensemble_name": ensemble_name,
                    "description": ensemble_description,
                    "members": configs,
                }
            ),
            indent=2,
        ),
        encoding="utf-8",
    )

    metric_rows: list[dict[str, Any]] = []
    regime_rows: list[dict[str, Any]] = []
    for weighting, ensemble_col in [("equal", score_equal), ("weighted", score_weighted)]:
        for split, mask in split_masks.items():
            part = merged.loc[mask].copy()
            if part.empty:
                continue
            metrics = rmp.evaluate_scores(
                part,
                ensemble_col,
                rmp.EVAL_TARGET_COL,
                rmp.EVAL_RETURN_COL,
                eval_args,
                split,
                target_dir,
            )
            regimes = rmp.evaluate_regimes(
                part,
                ensemble_col,
                rmp.EVAL_TARGET_COL,
                rmp.EVAL_RETURN_COL,
                eval_args,
                target_dir,
                split,
            )
            (target_dir / f"{ensemble_col}_{split}_regime_metrics.json").write_text(
                json.dumps(rmp.clean_json(regimes), indent=2, allow_nan=False),
                encoding="utf-8",
            )
            base = {
                "target_col": target_col,
                "ensemble_name": ensemble_name,
                "weighting": weighting,
                "score": ensemble_col,
                "split": split,
                "n_members": len(configs),
                "member_models": ",".join(sorted({str(c["model"]) for c in configs})),
                "member_variants": ",".join(sorted({str(c["feature_variant"]) for c in configs})),
            }
            metric_rows.append(
                {
                    **base,
                    **{k: safe_float(v) for k, v in metrics.items() if isinstance(v, (int, float, np.integer, np.floating))},
                }
            )
            for regime_name, regime_metrics in regimes.items():
                regime_rows.append(
                    {
                        **base,
                        "regime": regime_name,
                        **{
                            k: safe_float(v)
                            for k, v in regime_metrics.items()
                            if isinstance(v, (int, float, np.integer, np.floating))
                        },
                    }
                )
    return metric_rows, regime_rows


def evaluate_ensembles(
    best: pd.DataFrame, out_root: Path, experiment_name: str, args: argparse.Namespace
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if best.empty or not {"score", "split"}.issubset(best.columns):
        return pd.DataFrame(), pd.DataFrame()
    val = best.loc[(best["score"] == "model_score") & (best["split"] == "val")].copy()
    if val.empty:
        return pd.DataFrame(), pd.DataFrame()
    ensemble_root = out_root / f"{experiment_name}_ensembles"
    ensemble_root.mkdir(parents=True, exist_ok=True)
    metric_rows = []
    regime_rows = []
    for target_col, target_rows in val.groupby("target_col", sort=True):
        selected = target_rows.sort_values(args.selection_metric, ascending=False)
        for spec in ensemble_definitions(selected, out_root, args):
            rows, regimes = evaluate_single_ensemble(
                spec["rows"],
                out_root,
                target_col,
                spec["name"],
                spec["description"],
                spec["stability"],
                args,
            )
            metric_rows.extend(rows)
            regime_rows.extend(regimes)
    out = pd.DataFrame(metric_rows)
    if not out.empty:
        out.to_csv(out_root / f"{experiment_name}_ensemble_metrics.csv", index=False)
    regime_out = pd.DataFrame(regime_rows)
    if not regime_out.empty:
        regime_out.to_csv(out_root / f"{experiment_name}_ensemble_regime_metrics.csv", index=False)
    return out, regime_out


def write_report(
    summary: pd.DataFrame,
    best: pd.DataFrame,
    ensemble: pd.DataFrame,
    ensemble_regime: pd.DataFrame,
    out_root: Path,
    args: argparse.Namespace,
) -> None:
    lines = [
        "# Validation Ensemble Search Report",
        "",
        f"- Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Experiment: `{args.experiment_name}`",
        f"- Selection metric: `{args.selection_metric}` on validation `model_score`",
        f"- Candidate metric rows: {len(summary)}",
        "",
        "## Best Single Models",
        "",
    ]
    if best.empty or not {"score", "split"}.issubset(best.columns):
        merged = pd.DataFrame()
    else:
        best_test = best.loc[(best["score"] == "model_score") & (best["split"] == "test")].copy()
        best_val = best.loc[(best["score"] == "model_score") & (best["split"] == "val")][
            ["run_name", "mean_rank_ic", "rank_ic_ir", "mean_ic", "ic_ir", "sharpe_net"]
        ].rename(
            columns={
                "mean_rank_ic": "val_rank_ic",
                "rank_ic_ir": "val_rank_icir",
                "mean_ic": "val_ic",
                "ic_ir": "val_icir",
                "sharpe_net": "val_sharpe",
            }
        )
        merged = best_test.merge(best_val, on="run_name", how="left")
    if merged.empty:
        lines.append("_No completed single-model runs yet._")
    else:
        cols = [
            "target_col", "model", "feature_variant", "grid_tag",
            "val_rank_ic", "val_rank_icir", "val_ic", "val_icir", "val_sharpe",
            "mean_rank_ic", "rank_ic_ir", "mean_ic", "ic_ir", "sharpe_net", "ann_return_net",
        ]
        lines.append(merged[cols].sort_values(["target_col", "model", "feature_variant"]).to_markdown(index=False, floatfmt=".4f"))
    lines.extend(["", "## Rank Ensembles", ""])
    if ensemble.empty:
        lines.append("_No ensemble metrics yet._")
    else:
        cols = [
            "target_col", "ensemble_name", "weighting", "split", "n_members",
            "mean_rank_ic", "rank_ic_ir", "mean_ic", "ic_ir", "sharpe_net",
            "ann_return_net", "avg_turnover", "max_drawdown_net",
        ]
        lines.append(
            ensemble[cols]
            .sort_values(["target_col", "ensemble_name", "weighting", "split"])
            .to_markdown(index=False, floatfmt=".4f")
        )
    lines.extend(["", "## Regime Ensemble Metrics", ""])
    if ensemble_regime.empty:
        lines.append("_No ensemble regime metrics yet._")
    else:
        cols = [
            "target_col", "ensemble_name", "weighting", "split", "regime",
            "mean_rank_ic", "rank_ic_ir", "sharpe_net", "ann_return_net", "max_drawdown_net",
        ]
        lines.append(
            ensemble_regime[cols]
            .sort_values(["target_col", "ensemble_name", "weighting", "split", "regime"])
            .to_markdown(index=False, floatfmt=".4f")
        )
    lines.extend(
        [
            "",
            "## Ensemble Definitions",
            "",
            "- `ensemble_all_val_selected`: current validation-selected best run per target/model/feature variant.",
            "- `ensemble_mlp_gated`: validation-selected members where MLP is included only when it passes validation stability gates.",
            "- `ensemble_no_mlp`: validation-selected members excluding all MLP runs.",
            "- `ensemble_tree_only`: validation-selected Ridge, LightGBM, and XGBoost members only.",
            "- `ensemble_supervised_graph_tree`: all-relation supervised_graph Ridge, LightGBM, and XGBoost members only.",
            "- `ensemble_graph_ablation_tree`: supervised graph relation-ablation Ridge, LightGBM, and XGBoost members only.",
            "- `ensemble_stability_filtered`: validation-selected members with positive full-validation rank IC, enough positive validation years, and non-negative available validation-regime rank IC.",
            "",
            "## Notes",
            "",
            "- Single-model hyperparameters are selected only from validation metrics.",
            "- Ensembles average daily cross-sectional prediction ranks from selected model predictions.",
            "- Test rows are evaluated after model and ensemble definition; they are not used for selection.",
            "- Regime rows are emitted only when the evaluated split overlaps a configured regime window.",
        ]
    )
    (out_root / f"{args.experiment_name}_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    tasks = build_tasks(args)
    (out_root / f"{args.experiment_name}_task_plan.json").write_text(
        json.dumps(clean_json(tasks), indent=2),
        encoding="utf-8",
    )

    if not args.skip_runs and not args.subprocess:
        run_tasks_in_process(tasks, args, out_root)
    elif not args.skip_runs:
        for i, task in enumerate(tasks, start=1):
            run_dir = out_root / task["run_name"]
            if run_done(run_dir) and not args.force:
                print(f"[{i}/{len(tasks)}] skip completed {task['run_name']}", flush=True)
                continue
            print(f"[{i}/{len(tasks)}] run {task['run_name']}", flush=True)
            start = time.time()
            rc = run_candidate(task, args, out_root)
            elapsed = time.time() - start
            print(f"[{i}/{len(tasks)}] finished rc={rc} elapsed={elapsed:.1f}s {task['run_name']}", flush=True)
            if rc != 0:
                raise SystemExit(rc)
            summary = extract_rows(out_root, args.experiment_name)
            summary.to_csv(out_root / f"{args.experiment_name}_all_metrics.csv", index=False)
            best = select_best(summary, args.selection_metric)
            best.to_csv(out_root / f"{args.experiment_name}_best_metrics.csv", index=False)

    summary = extract_rows(out_root, args.experiment_name)
    summary.to_csv(out_root / f"{args.experiment_name}_all_metrics.csv", index=False)
    best = select_best(summary, args.selection_metric)
    best.to_csv(out_root / f"{args.experiment_name}_best_metrics.csv", index=False)
    ensemble, ensemble_regime = evaluate_ensembles(best, out_root, args.experiment_name, args)
    write_report(summary, best, ensemble, ensemble_regime, out_root, args)
    print(f"Done. Report: {out_root / f'{args.experiment_name}_report.md'}")


if __name__ == "__main__":
    main()
