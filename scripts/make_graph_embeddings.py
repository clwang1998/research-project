#!/usr/bin/env python3
"""Create graph relation embeddings from sparse graph edges.

This is a dependency-light, deterministic graph relation encoder. It does not
train on future returns. Instead it uses relation-specific projections over the
constructed graph edges to produce node embeddings that can be joined back into
the tabular model.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from build_graph_edges import STYLE_FEATURES, standardize_date_features


RELATIONS = ["sector", "style_knn", "rolling_corr"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph-dir", default="data/processed/graphs")
    parser.add_argument("--feature-dir", default="data/processed/features_by_group")
    parser.add_argument("--out-dir", default="data/processed/graph_embeddings")
    parser.add_argument("--hidden-dim", type=int, default=16)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--compression", default="zstd")
    parser.add_argument("--skip-daily", action="store_true")
    parser.add_argument("--audit-path", default="data/processed/graph_feature_audit.json")
    return parser.parse_args()


def leaky_relu(x: np.ndarray, negative_slope: float = 0.2) -> np.ndarray:
    return np.where(x >= 0, x, negative_slope * x)


def softmax_1d(x: np.ndarray) -> np.ndarray:
    if x.size == 0:
        return x
    x = x - np.max(x)
    exp = np.exp(x)
    den = exp.sum()
    if not np.isfinite(den) or den <= 0:
        return np.full_like(x, 1.0 / len(x), dtype="float32")
    return (exp / den).astype("float32")


def layer_norm(x: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    mean = x.mean(axis=1, keepdims=True)
    std = x.std(axis=1, keepdims=True)
    return (x - mean) / (std + eps)


def init_params(input_dim: int, hidden_dim: int, seed: int) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    params: dict[str, object] = {
        "layer1": {},
        "layer2": {},
        "rel_query1": rng.normal(0, 0.4, size=hidden_dim).astype("float32"),
        "rel_query2": rng.normal(0, 0.4, size=hidden_dim).astype("float32"),
        "self1": rng.normal(0, 1 / np.sqrt(input_dim), size=(input_dim, hidden_dim)).astype("float32"),
        "self2": rng.normal(0, 1 / np.sqrt(hidden_dim), size=(hidden_dim, hidden_dim)).astype("float32"),
    }
    for layer_name, in_dim in [("layer1", input_dim), ("layer2", hidden_dim)]:
        layer: dict[str, dict[str, np.ndarray]] = {}
        for rel in RELATIONS:
            layer[rel] = {
                "W": rng.normal(0, 1 / np.sqrt(in_dim), size=(in_dim, hidden_dim)).astype("float32"),
                "a_src": rng.normal(0, 0.4, size=hidden_dim).astype("float32"),
                "a_dst": rng.normal(0, 0.4, size=hidden_dim).astype("float32"),
            }
        params[layer_name] = layer
    return params


def aggregate_relation(
    h: np.ndarray,
    edges: pd.DataFrame,
    symbol_to_idx: dict[str, int],
    rel_params: dict[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    n = h.shape[0]
    hidden = h.shape[1]
    out = np.zeros((n, hidden), dtype="float32")
    degree = np.zeros(n, dtype="int16")
    if edges.empty:
        return out, degree

    src_idx = edges["src"].astype(str).map(symbol_to_idx).to_numpy()
    dst_idx = edges["dst"].astype(str).map(symbol_to_idx).to_numpy()
    valid = pd.notna(src_idx) & pd.notna(dst_idx)
    if not valid.any():
        return out, degree

    src_idx = src_idx[valid].astype("int64")
    dst_idx = dst_idx[valid].astype("int64")
    weights = edges.loc[valid, "weight"].to_numpy(dtype="float32")
    scores = (
        h[src_idx] @ rel_params["a_src"]
        + h[dst_idx] @ rel_params["a_dst"]
        + np.log(np.clip(weights, 1e-6, None))
    )
    scores = leaky_relu(scores.astype("float32"))

    order = np.argsort(src_idx, kind="mergesort")
    src_idx = src_idx[order]
    dst_idx = dst_idx[order]
    scores = scores[order]

    start = 0
    while start < len(src_idx):
        end = start + 1
        src = src_idx[start]
        while end < len(src_idx) and src_idx[end] == src:
            end += 1
        alpha = softmax_1d(scores[start:end])
        out[src] = alpha @ h[dst_idx[start:end]]
        degree[src] = end - start
        start = end
    return out, degree


def graph_relation_layer(
    x: np.ndarray,
    edges_by_relation: dict[str, pd.DataFrame],
    symbol_to_idx: dict[str, int],
    layer_params: dict[str, dict[str, np.ndarray]],
    rel_query: np.ndarray,
    self_w: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    rel_outputs = []
    rel_degrees = []
    for rel in RELATIONS:
        rel_param = layer_params[rel]
        h_rel = np.tanh(x @ rel_param["W"]).astype("float32")
        agg, degree = aggregate_relation(h_rel, edges_by_relation.get(rel), symbol_to_idx, rel_param)
        rel_outputs.append(agg)
        rel_degrees.append(degree)

    rel_stack = np.stack(rel_outputs, axis=1)  # n x relation x hidden
    degrees = np.stack(rel_degrees, axis=1)
    rel_scores = rel_stack @ rel_query
    rel_scores = np.where(degrees > 0, rel_scores, -1e9)
    all_missing = (degrees.sum(axis=1) == 0)
    rel_weights = np.apply_along_axis(softmax_1d, 1, rel_scores).astype("float32")
    if all_missing.any():
        rel_weights[all_missing] = 1.0 / len(RELATIONS)

    fused = (rel_stack * rel_weights[:, :, None]).sum(axis=1)
    residual = x @ self_w
    out = np.tanh(layer_norm(fused + residual)).astype("float32")
    return out, rel_weights


def load_edges(graph_dir: Path) -> dict[str, dict[pd.Timestamp, pd.DataFrame]]:
    specs = {
        "sector": "sector_edges.parquet",
        "style_knn": "style_knn_edges.parquet",
        "rolling_corr": "rolling_corr_edges.parquet",
    }
    out: dict[str, dict[pd.Timestamp, pd.DataFrame]] = {}
    for rel, filename in specs.items():
        df = pd.read_parquet(graph_dir / filename)
        df["date"] = pd.to_datetime(df["date"])
        out[rel] = {pd.Timestamp(k): v for k, v in df.groupby("date", sort=False)}
    return out


def make_rebalance_embeddings(
    node: pd.DataFrame,
    edges: dict[str, dict[pd.Timestamp, pd.DataFrame]],
    hidden_dim: int,
    seed: int,
) -> pd.DataFrame:
    params = init_params(len(STYLE_FEATURES), hidden_dim, seed)
    frames: list[pd.DataFrame] = []
    for i, (date, day) in enumerate(node.groupby("date", sort=True), start=1):
        day = day.sort_values("symbol", kind="mergesort").reset_index(drop=True)
        symbols = day["symbol"].astype(str).to_numpy()
        symbol_to_idx = {sym: idx for idx, sym in enumerate(symbols)}
        x = standardize_date_features(day[STYLE_FEATURES].to_numpy())
        edge_day = {
            rel: rel_dates.get(pd.Timestamp(date), pd.DataFrame())
            for rel, rel_dates in edges.items()
        }
        h1, _rel_w1 = graph_relation_layer(
            x,
            edge_day,
            symbol_to_idx,
            params["layer1"],
            params["rel_query1"],
            params["self1"],
        )
        h2, rel_w2 = graph_relation_layer(
            h1,
            edge_day,
            symbol_to_idx,
            params["layer2"],
            params["rel_query2"],
            params["self2"],
        )
        emb_cols = {f"graph_emb_{j}": h2[:, j].astype("float32") for j in range(hidden_dim)}
        rel_cols = {
            f"graph_rel_weight_{rel}": rel_w2[:, r].astype("float32")
            for r, rel in enumerate(RELATIONS)
        }
        frames.append(
            pd.DataFrame(
                {
                    "date": pd.Timestamp(date),
                    "symbol": symbols,
                    **emb_cols,
                    **rel_cols,
                }
            )
        )
        if i % 50 == 0:
            print(
                json.dumps(
                    {
                        "embedded_rebalance_dates": i,
                        "latest_date": str(pd.Timestamp(date).date()),
                    }
                ),
                flush=True,
            )
    emb = pd.concat(frames, ignore_index=True)
    emb["symbol"] = emb["symbol"].astype("category")
    return emb


def expand_to_daily(
    emb_rebalance: pd.DataFrame, feature_dir: Path, hidden_dim: int
) -> pd.DataFrame:
    keys = pd.read_parquet(
        feature_dir / "calendar_metadata.parquet",
        columns=["date", "symbol", "sector", "sub_industry", "hq_state", "hq_region"],
    )
    keys["symbol"] = keys["symbol"].astype(str)
    emb = emb_rebalance.copy()
    emb["symbol"] = emb["symbol"].astype(str)
    emb_cols = [f"graph_emb_{i}" for i in range(hidden_dim)] + [
        f"graph_rel_weight_{rel}" for rel in RELATIONS
    ]
    parts: list[pd.DataFrame] = []
    for symbol, key_part in keys.groupby("symbol", sort=False):
        emb_part = emb.loc[emb["symbol"] == symbol, ["date", *emb_cols]].sort_values("date")
        key_part = key_part.sort_values("date")
        if emb_part.empty:
            merged = key_part.copy()
            for col in emb_cols:
                merged[col] = np.nan
        else:
            merged = pd.merge_asof(
                key_part,
                emb_part,
                on="date",
                direction="backward",
            )
        parts.append(merged)
    out = pd.concat(parts, ignore_index=True)
    out["symbol"] = out["symbol"].astype("category")
    for col in ["sector", "sub_industry", "hq_state", "hq_region"]:
        out[col] = out[col].astype("category")
    for col in emb_cols:
        out[col] = out[col].astype("float32")
    return out


def build_daily_audit(daily: pd.DataFrame | None, hidden_dim: int) -> dict[str, object]:
    if daily is None:
        return {"daily_embeddings_written": False}

    emb_cols = [f"graph_emb_{i}" for i in range(hidden_dim)]
    rel_cols = [f"graph_rel_weight_{rel}" for rel in RELATIONS]
    feature_cols = emb_cols + rel_cols
    missing = daily[feature_cols].isna().any(axis=1)
    present = ~missing
    rel_sum = daily.loc[present, rel_cols].sum(axis=1) if present.any() else pd.Series(dtype="float32")
    first_date = daily.loc[present, "date"].min() if present.any() else pd.NaT
    last_date = daily.loc[present, "date"].max() if present.any() else pd.NaT
    return {
        "daily_embeddings_written": True,
        "daily_embedding_rows": int(len(daily)),
        "daily_embedding_dates": int(daily["date"].nunique()),
        "daily_embedding_symbols": int(daily["symbol"].nunique()),
        "rows_with_missing_embedding": int(missing.sum()),
        "missing_embedding_pct": float(missing.mean()) if len(daily) else 0.0,
        "first_embedding_date_by_any_symbol": None
        if pd.isna(first_date)
        else str(pd.Timestamp(first_date).date()),
        "last_embedding_date_by_any_symbol": None
        if pd.isna(last_date)
        else str(pd.Timestamp(last_date).date()),
        "relation_weight_sum_min": None if rel_sum.empty else float(rel_sum.min()),
        "relation_weight_sum_max": None if rel_sum.empty else float(rel_sum.max()),
    }


def write_graph_audit(
    audit_path: Path,
    edge_metadata: dict[str, object],
    embedding_metadata: dict[str, object],
    daily: pd.DataFrame | None,
    hidden_dim: int,
) -> None:
    audit = {
        "graph_edges": edge_metadata,
        "graph_embeddings": embedding_metadata,
        "daily_embedding_audit": build_daily_audit(daily, hidden_dim),
    }
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    start = time.perf_counter()
    graph_dir = Path(args.graph_dir)
    out_dir = Path(args.out_dir)
    feature_dir = Path(args.feature_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    edge_metadata_path = graph_dir / "graph_edge_metadata.json"
    edge_metadata = (
        json.loads(edge_metadata_path.read_text(encoding="utf-8"))
        if edge_metadata_path.exists()
        else {}
    )

    node = pd.read_parquet(graph_dir / "graph_node_features.parquet")
    node["date"] = pd.to_datetime(node["date"])
    node["symbol"] = node["symbol"].astype(str)
    edges = load_edges(graph_dir)
    emb_rebalance = make_rebalance_embeddings(node, edges, args.hidden_dim, args.seed)
    rebalance_path = out_dir / "graph_relation_embeddings_rebalance.parquet"
    emb_rebalance.to_parquet(rebalance_path, index=False, compression=args.compression)

    daily_path = None
    daily_rows = None
    daily = None
    if not args.skip_daily:
        daily = expand_to_daily(emb_rebalance, feature_dir, args.hidden_dim)
        daily_path = out_dir / "graph_relation_embeddings_daily.parquet"
        daily.to_parquet(daily_path, index=False, compression=args.compression)
        daily_rows = int(len(daily))

    feature_manifest = pd.DataFrame(
        [
            {
                "feature": f"graph_emb_{i}",
                "category": "graph_embedding",
                "description": "Deterministic graph relation embedding.",
            }
            for i in range(args.hidden_dim)
        ]
        + [
            {
                "feature": f"graph_rel_weight_{rel}",
                "category": "graph_embedding",
                "description": f"Second-layer relation fusion weight for {rel}.",
            }
            for rel in RELATIONS
        ]
    )
    manifest_path = out_dir / "graph_embedding_manifest.csv"
    feature_manifest.to_csv(manifest_path, index=False)

    metadata = {
        "encoder": "deterministic_graph_relation_encoder",
        "trained_on_targets": False,
        "relations": RELATIONS,
        "node_features": STYLE_FEATURES,
        "hidden_dim": args.hidden_dim,
        "seed": args.seed,
        "rebalance_rows": int(len(emb_rebalance)),
        "daily_rows": daily_rows,
        "files": {
            "rebalance_embeddings": str(rebalance_path),
            "daily_embeddings": None if daily_path is None else str(daily_path),
            "manifest": str(manifest_path),
        },
        "seconds": round(time.perf_counter() - start, 3),
    }
    metadata_path = out_dir / "graph_embedding_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    write_graph_audit(
        Path(args.audit_path),
        edge_metadata,
        metadata,
        daily,
        args.hidden_dim,
    )
    print(json.dumps(metadata, indent=2), flush=True)


if __name__ == "__main__":
    main()
