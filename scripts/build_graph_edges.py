#!/usr/bin/env python3
"""Build sparse multi-relation graph edges from the engineered S&P 500 panel.

Relations:
  - sector: same sector/sub-industry candidates, capped by nearest style distance.
  - style_knn: cross-sectional kNN in technical/style feature space.
  - rolling_corr: top rolling stock-stock return correlations.

Edges are stored as sparse edge lists. The convention is:
  src = target stock that receives information
  dst = neighbor stock that sends information
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd


CONTEXT_COLS = ["date", "symbol", "sector", "sub_industry"]
STYLE_FEATURES = [
    "ret_20d",
    "ret_60d",
    "ret_120d",
    "mom_252d_skip_21d",
    "vol_20d",
    "vol_60d",
    "downside_vol_20d",
    "volume_z_20d",
    "dollar_volume_z_20d",
    "amihud_20d",
    "rsi_14d",
    "sma_gap_20d",
    "sma_gap_50d",
    "boll_z_20d",
    "channel_pos_20d",
    "log_dollar_volume",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-dir", default="data/processed/features_by_group")
    parser.add_argument("--out-dir", default="data/processed/graphs")
    parser.add_argument("--rebalance-step", type=int, default=20)
    parser.add_argument("--min-history-days", type=int, default=252)
    parser.add_argument("--sector-k", type=int, default=10)
    parser.add_argument("--style-k", type=int, default=10)
    parser.add_argument("--corr-k", type=int, default=10)
    parser.add_argument("--corr-window", type=int, default=60)
    parser.add_argument("--min-corr", type=float, default=0.05)
    parser.add_argument("--compression", default="zstd")
    return parser.parse_args()


def read_group(base: Path, name: str, columns: list[str]) -> pd.DataFrame:
    return pd.read_parquet(base / f"{name}.parquet", columns=columns)


def choose_rebalance_dates(
    all_dates: pd.Series, min_history_days: int, step: int
) -> pd.DatetimeIndex:
    dates = pd.Index(pd.to_datetime(pd.Series(all_dates).drop_duplicates().sort_values()))
    if len(dates) <= min_history_days:
        raise ValueError("Not enough dates for requested min_history_days")
    chosen = list(dates[min_history_days::step])
    if dates[-1] not in chosen:
        chosen.append(dates[-1])
    return pd.DatetimeIndex(chosen)


def load_node_features(base: Path, rebalance_dates: pd.DatetimeIndex) -> pd.DataFrame:
    date_set = set(rebalance_dates)
    calendar = read_group(
        base, "calendar_metadata", ["date", "symbol", "sector", "sub_industry"]
    )
    calendar = calendar.loc[calendar["date"].isin(date_set)].copy()
    parts = [calendar]
    specs = {
        "price_momentum": [
            "date",
            "symbol",
            "ret_20d",
            "ret_60d",
            "ret_120d",
            "mom_252d_skip_21d",
            "log_dollar_volume",
        ],
        "volatility": ["date", "symbol", "vol_20d", "vol_60d", "downside_vol_20d"],
        "liquidity_volume": [
            "date",
            "symbol",
            "volume_z_20d",
            "dollar_volume_z_20d",
            "amihud_20d",
        ],
        "trend_technical": [
            "date",
            "symbol",
            "rsi_14d",
            "sma_gap_20d",
            "sma_gap_50d",
            "boll_z_20d",
            "channel_pos_20d",
        ],
    }
    node = parts[0]
    for group, cols in specs.items():
        part = read_group(base, group, cols)
        part = part.loc[part["date"].isin(date_set)].copy()
        node = node.merge(part, on=["date", "symbol"], how="left", sort=False)

    node["symbol"] = node["symbol"].astype(str)
    node["sector"] = node["sector"].astype(str)
    node["sub_industry"] = node["sub_industry"].astype(str)
    node = node.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)
    return node


def standardize_date_features(x: np.ndarray) -> np.ndarray:
    x = x.astype("float32", copy=True)
    finite = np.isfinite(x)
    means = np.nanmean(np.where(finite, x, np.nan), axis=0)
    stds = np.nanstd(np.where(finite, x, np.nan), axis=0)
    means = np.where(np.isfinite(means), means, 0.0)
    stds = np.where((stds > 1e-8) & np.isfinite(stds), stds, 1.0)
    x = (np.where(finite, x, means) - means) / stds
    return np.clip(x, -6.0, 6.0).astype("float32")


def squared_distances(x: np.ndarray) -> np.ndarray:
    norms = np.sum(x * x, axis=1, keepdims=True)
    d2 = norms + norms.T - 2.0 * (x @ x.T)
    return np.maximum(d2, 0.0)


def topk_from_scores(scores: np.ndarray, k: int, largest: bool) -> np.ndarray:
    if scores.size == 0:
        return np.array([], dtype=np.int64)
    k = min(k, scores.size)
    if largest:
        idx = np.argpartition(-scores, k - 1)[:k]
        idx = idx[np.argsort(-scores[idx])]
    else:
        idx = np.argpartition(scores, k - 1)[:k]
        idx = idx[np.argsort(scores[idx])]
    return idx.astype(np.int64)


def make_sector_edges(
    date: pd.Timestamp,
    symbols: np.ndarray,
    sectors: np.ndarray,
    subinds: np.ndarray,
    d2: np.ndarray,
    k: int,
) -> pd.DataFrame:
    srcs: list[str] = []
    dsts: list[str] = []
    weights: list[float] = []
    ranks: list[int] = []
    edge_subtype: list[str] = []
    for i, src in enumerate(symbols):
        same_sector = sectors == sectors[i]
        same_sub = subinds == subinds[i]
        candidate_mask = same_sector.copy()
        candidate_mask[i] = False
        candidates = np.flatnonzero(candidate_mask)
        if candidates.size == 0:
            continue
        # Prefer sub-industry peers, then nearest same-sector peers.
        score = d2[i, candidates] - same_sub[candidates].astype("float32") * 2.0
        chosen = candidates[topk_from_scores(score, k, largest=False)]
        for rank, j in enumerate(chosen, start=1):
            subtype = "same_sub_industry" if same_sub[j] else "same_sector"
            base = 1.0 if same_sub[j] else 0.75
            weight = base * float(np.exp(-d2[i, j] / 8.0))
            srcs.append(src)
            dsts.append(symbols[j])
            weights.append(weight)
            ranks.append(rank)
            edge_subtype.append(subtype)
    return pd.DataFrame(
        {
            "date": date,
            "src": srcs,
            "dst": dsts,
            "relation": "sector",
            "edge_subtype": edge_subtype,
            "weight": np.asarray(weights, dtype="float32"),
            "rank": np.asarray(ranks, dtype="int16"),
        }
    )


def make_style_edges(
    date: pd.Timestamp, symbols: np.ndarray, d2: np.ndarray, k: int
) -> pd.DataFrame:
    srcs: list[str] = []
    dsts: list[str] = []
    weights: list[float] = []
    ranks: list[int] = []
    n = len(symbols)
    for i, src in enumerate(symbols):
        scores = d2[i].copy()
        scores[i] = np.inf
        chosen = topk_from_scores(scores, k, largest=False)
        for rank, j in enumerate(chosen, start=1):
            srcs.append(src)
            dsts.append(symbols[j])
            weights.append(float(np.exp(-scores[j] / 8.0)))
            ranks.append(rank)
    return pd.DataFrame(
        {
            "date": date,
            "src": srcs,
            "dst": dsts,
            "relation": "style_knn",
            "edge_subtype": "style_nearest",
            "weight": np.asarray(weights, dtype="float32"),
            "rank": np.asarray(ranks, dtype="int16"),
        }
    )


def rolling_corr_matrix(
    ret_wide: pd.DataFrame, date: pd.Timestamp, window: int
) -> tuple[np.ndarray, np.ndarray]:
    pos = ret_wide.index.get_indexer([date])[0]
    start = max(0, pos - window + 1)
    block = ret_wide.iloc[start : pos + 1]
    symbols = block.columns.astype(str).to_numpy()
    arr = block.to_numpy(dtype="float32")
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    if arr.shape[0] < 5:
        return symbols, np.eye(arr.shape[1], dtype="float32")
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = np.corrcoef(arr, rowvar=False).astype("float32")
    corr = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)
    return symbols, corr


def make_corr_edges(
    date: pd.Timestamp,
    symbols: np.ndarray,
    corr_symbols: np.ndarray,
    corr: np.ndarray,
    k: int,
    min_corr: float,
) -> pd.DataFrame:
    corr_pos = {sym: i for i, sym in enumerate(corr_symbols)}
    srcs: list[str] = []
    dsts: list[str] = []
    weights: list[float] = []
    ranks: list[int] = []
    for src in symbols:
        i = corr_pos.get(src)
        if i is None:
            continue
        row = corr[i].copy()
        row[i] = -np.inf
        row = np.where(row >= min_corr, row, -np.inf)
        finite = np.isfinite(row)
        if not finite.any():
            continue
        candidates = np.flatnonzero(finite)
        chosen_local = candidates[topk_from_scores(row[candidates], k, largest=True)]
        for rank, j in enumerate(chosen_local, start=1):
            srcs.append(src)
            dsts.append(corr_symbols[j])
            weights.append(float(row[j]))
            ranks.append(rank)
    return pd.DataFrame(
        {
            "date": date,
            "src": srcs,
            "dst": dsts,
            "relation": "rolling_corr",
            "edge_subtype": f"corr_{len(corr_symbols)}x",
            "weight": np.asarray(weights, dtype="float32"),
            "rank": np.asarray(ranks, dtype="int16"),
        }
    )


def write_edge_file(frames: list[pd.DataFrame], path: Path, compression: str) -> dict[str, int]:
    edge = pd.concat(frames, ignore_index=True)
    for col in ["src", "dst", "relation", "edge_subtype"]:
        edge[col] = edge[col].astype("category")
    edge.to_parquet(path, index=False, compression=compression)
    return {"rows": int(len(edge)), "columns": int(edge.shape[1])}


def main() -> None:
    args = parse_args()
    start_time = time.perf_counter()
    base = Path(args.feature_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    price_dates = read_group(base, "price_momentum", ["date"])
    rebalance_dates = choose_rebalance_dates(
        price_dates["date"], args.min_history_days, args.rebalance_step
    )
    node = load_node_features(base, rebalance_dates)
    node_path = out_dir / "graph_node_features.parquet"
    node_out = node.copy()
    node_out["symbol"] = node_out["symbol"].astype("category")
    node_out["sector"] = node_out["sector"].astype("category")
    node_out["sub_industry"] = node_out["sub_industry"].astype("category")
    node_out.to_parquet(node_path, index=False, compression=args.compression)

    returns = read_group(base, "price_momentum", ["date", "symbol", "ret_1d"])
    ret_wide = (
        returns.pivot(index="date", columns="symbol", values="ret_1d")
        .sort_index()
        .astype("float32")
    )

    sector_frames: list[pd.DataFrame] = []
    style_frames: list[pd.DataFrame] = []
    corr_frames: list[pd.DataFrame] = []

    grouped = node.groupby("date", sort=True)
    for idx, (date, day) in enumerate(grouped, start=1):
        day = day.sort_values("symbol", kind="mergesort")
        symbols = day["symbol"].astype(str).to_numpy()
        x = standardize_date_features(day[STYLE_FEATURES].to_numpy())
        d2 = squared_distances(x)
        sector_frames.append(
            make_sector_edges(
                date,
                symbols,
                day["sector"].astype(str).to_numpy(),
                day["sub_industry"].astype(str).to_numpy(),
                d2,
                args.sector_k,
            )
        )
        style_frames.append(make_style_edges(date, symbols, d2, args.style_k))
        corr_symbols, corr = rolling_corr_matrix(ret_wide, date, args.corr_window)
        corr_frames.append(
            make_corr_edges(date, symbols, corr_symbols, corr, args.corr_k, args.min_corr)
        )
        if idx % 50 == 0:
            print(
                json.dumps(
                    {
                        "processed_rebalance_dates": idx,
                        "latest_date": str(pd.Timestamp(date).date()),
                    }
                ),
                flush=True,
            )

    files = {
        "graph_node_features": {
            "path": str(node_path),
            "rows": int(len(node)),
            "columns": int(node.shape[1]),
        },
        "sector_edges": write_edge_file(
            sector_frames, out_dir / "sector_edges.parquet", args.compression
        ),
        "style_knn_edges": write_edge_file(
            style_frames, out_dir / "style_knn_edges.parquet", args.compression
        ),
        "rolling_corr_edges": write_edge_file(
            corr_frames, out_dir / "rolling_corr_edges.parquet", args.compression
        ),
    }
    for name in ["sector_edges", "style_knn_edges", "rolling_corr_edges"]:
        files[name]["path"] = str(out_dir / f"{name}.parquet")

    metadata = {
        "relation_types": ["sector", "style_knn", "rolling_corr"],
        "edge_convention": "src receives information from dst",
        "rebalance_dates": int(len(rebalance_dates)),
        "rebalance_step": args.rebalance_step,
        "min_history_days": args.min_history_days,
        "sector_k": args.sector_k,
        "style_k": args.style_k,
        "corr_k": args.corr_k,
        "corr_window": args.corr_window,
        "min_corr": args.min_corr,
        "style_features": STYLE_FEATURES,
        "files": files,
        "seconds": round(time.perf_counter() - start_time, 3),
    }
    metadata_path = out_dir / "graph_edge_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2), flush=True)


if __name__ == "__main__":
    main()
