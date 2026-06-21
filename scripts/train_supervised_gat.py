#!/usr/bin/env python3
"""Train leakage-safe supervised relation-aware GAT embeddings.

Each training sample is one date's cross-sectional stock graph. The graph
structure and node features use information available at that date; forward
returns are used only as supervised labels. The script writes graph-date
predictions/embeddings plus a daily as-of expanded OOF embedding panel for
downstream tabular models.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.nn import functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_model_pipeline as rmp  # noqa: E402


RELATIONS = ["sector", "style_knn", "rolling_corr"]
SUPERVISED_SCORE_COL = "supervised_graph_score"
SUPERVISED_EMB_PREFIX = "supervised_graph_emb_"
SUPERVISED_REL_PREFIX = "supervised_graph_rel_weight_"


@dataclass
class FoldStats:
    feature_cols: list[str]
    medians: np.ndarray
    means: np.ndarray
    stds: np.ndarray
    y_mean: float
    y_std: float

    def transform_x(self, df: pd.DataFrame) -> np.ndarray:
        x = df.loc[:, self.feature_cols].to_numpy(dtype=np.float32, copy=True)
        x[~np.isfinite(x)] = np.nan
        if np.isnan(x).any():
            inds = np.where(np.isnan(x))
            x[inds] = np.take(self.medians, inds[1]).astype(np.float32)
        x = (x - self.means.astype(np.float32)) / self.stds.astype(np.float32)
        x[~np.isfinite(x)] = 0.0
        return x.astype(np.float32, copy=False)

    def transform_y(self, y: np.ndarray) -> np.ndarray:
        return ((y.astype(np.float32) - self.y_mean) / self.y_std).astype(np.float32)

    def inverse_y(self, y: np.ndarray) -> np.ndarray:
        return (y.astype(np.float32) * self.y_std + self.y_mean).astype(np.float32)


@dataclass
class GraphSample:
    date: pd.Timestamp
    symbols: np.ndarray
    sectors: np.ndarray
    x: torch.Tensor
    y: torch.Tensor
    ret: torch.Tensor
    edges: dict[str, tuple[torch.Tensor, torch.Tensor, torch.Tensor]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-dir", default="data/processed/features_by_group")
    parser.add_argument("--feature-map", default="data/processed/feature_columns_by_group.csv")
    parser.add_argument("--graph-dir", default="data/processed/graphs")
    parser.add_argument("--out-dir", default="data/processed/supervised_graph_embeddings")
    parser.add_argument("--run-name", default=None)
    parser.add_argument("--target-col", default="target_excess_sector_fwd_5d")
    parser.add_argument("--return-col", default="target_ret_fwd_5d")
    parser.add_argument("--feature-set", choices=["core", "all"], default="core")
    parser.add_argument("--feature-groups", nargs="*", default=None)
    parser.add_argument("--max-lookback-days", type=int, default=None)
    parser.add_argument("--start-date", default="2001-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--train-end", default="2018-12-31")
    parser.add_argument("--val-end", default="2021-12-31")
    parser.add_argument("--first-oof-train-end", default="2012-12-31")
    parser.add_argument("--oof-step-years", type=int, default=1)
    parser.add_argument("--oof-early-stop-years", type=int, default=1)
    parser.add_argument("--execution-lag-days", type=int, default=1)
    parser.add_argument("--embargo-days", type=int, default=None)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--embedding-dim", type=int, default=16)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--patience", type=int, default=6)
    parser.add_argument("--batch-dates", type=int, default=4)
    parser.add_argument("--loss", choices=["huber", "mse", "huber_rank"], default="huber")
    parser.add_argument("--rank-loss-weight", type=float, default=0.1)
    parser.add_argument("--rank-pairs-per-date", type=int, default=4096)
    parser.add_argument("--huber-delta", type=float, default=1.0)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-names-per-date", type=int, default=100)
    parser.add_argument("--long-short-pct", type=float, default=0.10)
    parser.add_argument("--transaction-cost-bps", type=float, default=5.0)
    parser.add_argument("--rebalance-every", type=int, default=None)
    parser.add_argument("--sector-neutral", action="store_true")
    parser.add_argument("--max-symbols", type=int, default=None)
    parser.add_argument("--max-graph-dates", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def now_run_name() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def resolve_device(name: str) -> torch.device:
    if name == "cuda":
        return torch.device("cuda")
    if name == "mps":
        return torch.device("mps")
    if name == "cpu":
        return torch.device("cpu")
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def relation_path(graph_dir: Path, relation: str) -> Path:
    return graph_dir / f"{relation}_edges.parquet"


def load_edges(graph_dir: Path) -> dict[str, dict[pd.Timestamp, pd.DataFrame]]:
    out: dict[str, dict[pd.Timestamp, pd.DataFrame]] = {}
    for rel in RELATIONS:
        df = pd.read_parquet(relation_path(graph_dir, rel))
        df["date"] = pd.to_datetime(df["date"])
        out[rel] = {pd.Timestamp(k): v.copy() for k, v in df.groupby("date", sort=False)}
    return out


def edge_dates(edges: dict[str, dict[pd.Timestamp, pd.DataFrame]]) -> pd.DatetimeIndex:
    dates: set[pd.Timestamp] = set()
    for by_date in edges.values():
        dates.update(by_date.keys())
    return pd.DatetimeIndex(sorted(dates))


def load_gat_panel(
    args: argparse.Namespace,
    graph_dates: pd.DatetimeIndex,
    feature_cols: list[str],
) -> tuple[pd.DataFrame, list[str], pd.DatetimeIndex]:
    feature_dir = Path(args.feature_dir)
    target_cols = [args.target_col, args.return_col]
    target_read_cols = rmp.KEY_COLS + rmp.META_COLS + list(dict.fromkeys(target_cols))
    targets = pd.read_parquet(feature_dir / "targets.parquet", columns=target_read_cols)
    targets["date"] = pd.to_datetime(targets["date"])
    if args.start_date:
        targets = targets.loc[targets["date"] >= pd.Timestamp(args.start_date)]
    if args.end_date:
        targets = targets.loc[targets["date"] <= pd.Timestamp(args.end_date)]
    daily_calendar = pd.DatetimeIndex(sorted(targets["date"].drop_duplicates()))

    horizon_days = rmp.infer_horizon_days(args.target_col, args.return_col)
    targets = rmp.attach_effective_labels(
        targets,
        args.target_col,
        args.return_col,
        horizon_days,
        args.execution_lag_days,
    )
    graph_date_set = set(pd.to_datetime(graph_dates))
    panel = targets.loc[targets["date"].isin(graph_date_set)].copy()

    fmap = rmp.read_feature_map(args.feature_map)
    by_file = (
        fmap.loc[fmap["column"].isin(feature_cols)]
        .groupby("file")["column"]
        .apply(list)
        .to_dict()
    )
    for file_name, cols in sorted(by_file.items()):
        part = pd.read_parquet(feature_dir / file_name, columns=rmp.KEY_COLS + cols)
        part["date"] = pd.to_datetime(part["date"])
        part = part.loc[part["date"].isin(graph_date_set)].copy()
        panel = panel.merge(part, on=rmp.KEY_COLS, how="left", sort=False)
        del part

    numeric_cols: list[str] = []
    skipped: list[str] = []
    for col in feature_cols:
        if col in panel.columns and pd.api.types.is_numeric_dtype(panel[col]):
            numeric_cols.append(col)
        else:
            skipped.append(col)
    if skipped:
        print(f"Skipped {len(skipped)} non-numeric or missing feature columns.")
    if not numeric_cols:
        raise ValueError("No numeric node features available for GAT training.")

    if args.max_symbols:
        keep_symbols = sorted(panel["symbol"].astype(str).unique())[: args.max_symbols]
        panel = panel.loc[panel["symbol"].astype(str).isin(keep_symbols)].copy()

    panel = panel.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)
    panel["symbol"] = panel["symbol"].astype(str)
    return panel, numeric_cols, daily_calendar


def trading_pos(calendar: pd.DatetimeIndex, date: pd.Timestamp, side: str = "pad") -> int:
    if side == "pad":
        pos = calendar.searchsorted(pd.Timestamp(date), side="right") - 1
    else:
        pos = calendar.searchsorted(pd.Timestamp(date), side="left")
    return int(np.clip(pos, 0, len(calendar) - 1))


def keep_after_embargo(
    dates: pd.Series,
    calendar: pd.DatetimeIndex,
    boundary: pd.Timestamp,
    embargo_days: int,
) -> np.ndarray:
    if embargo_days <= 0:
        return np.ones(len(dates), dtype=bool)
    bpos = trading_pos(calendar, boundary, "pad")
    positions = calendar.searchsorted(pd.to_datetime(dates).to_numpy(), side="left")
    return positions > bpos + embargo_days


def split_masks(
    panel: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    train_end: str,
    val_end: str,
    embargo_days: int,
) -> dict[str, np.ndarray]:
    train_ts = pd.Timestamp(train_end)
    val_ts = pd.Timestamp(val_end)
    data_end = pd.Timestamp(panel["date"].max())
    label_end = pd.to_datetime(panel[rmp.LABEL_END_DATE_COL])
    dates = pd.to_datetime(panel["date"])
    train = (dates <= train_ts).to_numpy() & (label_end <= train_ts).to_numpy()
    val = (
        (dates > train_ts).to_numpy()
        & (dates <= val_ts).to_numpy()
        & (label_end <= val_ts).to_numpy()
        & keep_after_embargo(dates, calendar, train_ts, embargo_days)
    )
    test = (
        (dates > val_ts).to_numpy()
        & (label_end <= data_end).to_numpy()
        & keep_after_embargo(dates, calendar, val_ts, embargo_days)
    )
    return {"train": train, "val": val, "test": test}


def date_values(panel: pd.DataFrame, mask: np.ndarray) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(sorted(pd.to_datetime(panel.loc[mask, "date"]).drop_duplicates()))


def fit_stats(panel: pd.DataFrame, feature_cols: list[str], train_dates: pd.DatetimeIndex) -> FoldStats:
    mask = panel["date"].isin(train_dates).to_numpy()
    if not mask.any():
        raise ValueError("Cannot fit fold stats with an empty train date set.")
    x = panel.loc[mask, feature_cols].to_numpy(dtype=np.float32, copy=True)
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
    y = panel.loc[mask, rmp.EVAL_TARGET_COL].to_numpy(dtype=np.float32)
    y = y[np.isfinite(y)]
    y_mean = float(np.mean(y)) if len(y) else 0.0
    y_std = float(np.std(y)) if len(y) else 1.0
    if not np.isfinite(y_std) or y_std <= 1e-12:
        y_std = 1.0
    return FoldStats(feature_cols, medians, means, stds, y_mean, y_std)


def build_edge_tensors(
    edge_day: pd.DataFrame,
    symbol_to_idx: dict[str, int],
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    if edge_day.empty:
        empty_i = torch.empty(0, dtype=torch.long, device=device)
        empty_w = torch.empty(0, dtype=torch.float32, device=device)
        return empty_i, empty_i, empty_w
    src = edge_day["src"].astype(str).map(symbol_to_idx)
    dst = edge_day["dst"].astype(str).map(symbol_to_idx)
    valid = src.notna() & dst.notna()
    if not valid.any():
        empty_i = torch.empty(0, dtype=torch.long, device=device)
        empty_w = torch.empty(0, dtype=torch.float32, device=device)
        return empty_i, empty_i, empty_w
    src_t = torch.as_tensor(src.loc[valid].to_numpy(dtype=np.int64), dtype=torch.long, device=device)
    dst_t = torch.as_tensor(dst.loc[valid].to_numpy(dtype=np.int64), dtype=torch.long, device=device)
    weight_t = torch.as_tensor(
        edge_day.loc[valid, "weight"].to_numpy(dtype=np.float32, copy=True),
        dtype=torch.float32,
        device=device,
    ).clamp_min(1e-6)
    return src_t, dst_t, weight_t


def make_samples(
    panel: pd.DataFrame,
    edges: dict[str, dict[pd.Timestamp, pd.DataFrame]],
    dates: pd.DatetimeIndex,
    stats: FoldStats,
    device: torch.device,
) -> list[GraphSample]:
    samples: list[GraphSample] = []
    date_set = set(pd.to_datetime(dates))
    for date, day in panel.loc[panel["date"].isin(date_set)].groupby("date", sort=True):
        day = day.sort_values("symbol", kind="mergesort").reset_index(drop=True)
        if len(day) == 0:
            continue
        symbols = day["symbol"].astype(str).to_numpy()
        symbol_to_idx = {sym: i for i, sym in enumerate(symbols)}
        x = torch.as_tensor(stats.transform_x(day), dtype=torch.float32, device=device)
        y_np = stats.transform_y(day[rmp.EVAL_TARGET_COL].to_numpy(dtype=np.float32))
        ret_np = day[rmp.EVAL_RETURN_COL].to_numpy(dtype=np.float32)
        rel_edges = {
            rel: build_edge_tensors(
                edges[rel].get(pd.Timestamp(date), pd.DataFrame()),
                symbol_to_idx,
                device,
            )
            for rel in RELATIONS
        }
        samples.append(
            GraphSample(
                date=pd.Timestamp(date),
                symbols=symbols,
                sectors=day["sector"].astype(str).to_numpy(),
                x=x,
                y=torch.as_tensor(y_np, dtype=torch.float32, device=device),
                ret=torch.as_tensor(ret_np, dtype=torch.float32, device=device),
                edges=rel_edges,
            )
        )
    return samples


class RelationGATLayer(nn.Module):
    def __init__(self, in_dim: int, out_dim: int, relations: list[str], dropout: float) -> None:
        super().__init__()
        self.relations = relations
        self.dropout = nn.Dropout(dropout)
        self.rel_linears = nn.ModuleDict({rel: nn.Linear(in_dim, out_dim, bias=False) for rel in relations})
        self.att_src = nn.ParameterDict({rel: nn.Parameter(torch.empty(out_dim)) for rel in relations})
        self.att_dst = nn.ParameterDict({rel: nn.Parameter(torch.empty(out_dim)) for rel in relations})
        self.self_linear = nn.Linear(in_dim, out_dim, bias=False)
        self.fusion = nn.Sequential(
            nn.Linear(out_dim * (len(relations) + 1), out_dim),
            nn.ReLU(),
            nn.Linear(out_dim, len(relations)),
        )
        self.norm = nn.LayerNorm(out_dim)
        self.reset_parameters()

    def reset_parameters(self) -> None:
        for module in self.rel_linears.values():
            nn.init.xavier_uniform_(module.weight)
        nn.init.xavier_uniform_(self.self_linear.weight)
        for rel in self.relations:
            nn.init.normal_(self.att_src[rel], std=0.2)
            nn.init.normal_(self.att_dst[rel], std=0.2)

    def relation_attention(
        self,
        h: torch.Tensor,
        src: torch.Tensor,
        dst: torch.Tensor,
        weight: torch.Tensor,
        rel: str,
    ) -> torch.Tensor:
        out = torch.zeros_like(h)
        if src.numel() == 0:
            return out
        scores = (
            (h[src] * self.att_src[rel]).sum(dim=1)
            + (h[dst] * self.att_dst[rel]).sum(dim=1)
            + torch.log(weight.clamp_min(1e-6))
        )
        scores = F.leaky_relu(scores, negative_slope=0.2)
        max_per_src = torch.full(
            (h.shape[0],),
            -torch.inf,
            dtype=scores.dtype,
            device=scores.device,
        )
        max_per_src.scatter_reduce_(0, src, scores, reduce="amax", include_self=True)
        exp_scores = torch.exp(scores - max_per_src[src])
        denom = torch.zeros(h.shape[0], dtype=scores.dtype, device=scores.device)
        denom.scatter_add_(0, src, exp_scores)
        alpha = exp_scores / denom[src].clamp_min(1e-12)
        msg = h[dst] * alpha.unsqueeze(1)
        out.index_add_(0, src, msg)
        return out

    def forward(
        self,
        x: torch.Tensor,
        edges: dict[str, tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
    ) -> tuple[torch.Tensor, torch.Tensor]:
        rel_outputs = []
        degree_mask = []
        for rel in self.relations:
            h_rel = torch.tanh(self.rel_linears[rel](x))
            src, dst, weight = edges[rel]
            rel_outputs.append(self.relation_attention(h_rel, src, dst, weight, rel))
            degree = torch.zeros(x.shape[0], dtype=torch.bool, device=x.device)
            if src.numel() > 0:
                degree[src.unique()] = True
            degree_mask.append(degree)
        rel_stack = torch.stack(rel_outputs, dim=1)
        self_part = self.self_linear(x)
        fusion_input = torch.cat([rel_stack.flatten(1), self_part], dim=1)
        logits = self.fusion(self.dropout(fusion_input))
        mask = torch.stack(degree_mask, dim=1)
        logits = logits.masked_fill(~mask, -1e9)
        no_rel = ~mask.any(dim=1)
        if no_rel.any():
            logits = logits.clone()
            logits[no_rel] = 0.0
        rel_weight = torch.softmax(logits, dim=1)
        fused = (rel_stack * rel_weight.unsqueeze(-1)).sum(dim=1)
        out = torch.tanh(self.norm(fused + self_part))
        return self.dropout(out), rel_weight


class RelationAwareGAT(nn.Module):
    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        embedding_dim: int,
        relations: list[str],
        dropout: float,
    ) -> None:
        super().__init__()
        self.input_proj = nn.Sequential(nn.Linear(input_dim, hidden_dim), nn.ReLU(), nn.Dropout(dropout))
        self.gat1 = RelationGATLayer(hidden_dim, hidden_dim, relations, dropout)
        self.gat2 = RelationGATLayer(hidden_dim, embedding_dim, relations, dropout)
        self.pred = nn.Sequential(
            nn.Linear(hidden_dim + embedding_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
        )

    def forward(
        self,
        x: torch.Tensor,
        edges: dict[str, tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        base = self.input_proj(x)
        h1, _ = self.gat1(base, edges)
        emb, rel_weight = self.gat2(h1, edges)
        score = self.pred(torch.cat([base, emb], dim=1)).reshape(-1)
        return score, emb, rel_weight


def regression_loss(pred: torch.Tensor, target: torch.Tensor, args: argparse.Namespace) -> torch.Tensor:
    valid = torch.isfinite(target)
    if valid.sum() == 0:
        return pred.sum() * 0.0
    if args.loss == "mse":
        return F.mse_loss(pred[valid], target[valid])
    return F.huber_loss(pred[valid], target[valid], delta=args.huber_delta)


def pairwise_rank_loss(
    pred: torch.Tensor,
    target: torch.Tensor,
    max_pairs: int,
) -> torch.Tensor:
    valid = torch.isfinite(target)
    pred = pred[valid]
    target = target[valid]
    n = pred.numel()
    if n < 2:
        return pred.sum() * 0.0
    total_pairs = n * (n - 1)
    if total_pairs <= max_pairs:
        i = torch.arange(n, device=pred.device).repeat_interleave(n)
        j = torch.arange(n, device=pred.device).repeat(n)
    else:
        i = torch.randint(0, n, (max_pairs,), device=pred.device)
        j = torch.randint(0, n, (max_pairs,), device=pred.device)
    keep = target[i] != target[j]
    if keep.sum() == 0:
        return pred.sum() * 0.0
    i, j = i[keep], j[keep]
    sign = torch.sign(target[i] - target[j])
    return F.softplus(-(pred[i] - pred[j]) * sign).mean()


def sample_loss(
    model: RelationAwareGAT,
    sample: GraphSample,
    args: argparse.Namespace,
) -> torch.Tensor:
    pred, _, _ = model(sample.x, sample.edges)
    loss = regression_loss(pred, sample.y, args)
    if args.loss == "huber_rank" and args.rank_loss_weight > 0:
        loss = loss + args.rank_loss_weight * pairwise_rank_loss(
            pred, sample.y, args.rank_pairs_per_date
        )
    return loss


@torch.no_grad()
def eval_loss(model: RelationAwareGAT, samples: list[GraphSample], args: argparse.Namespace) -> float:
    if not samples:
        return math.inf
    model.eval()
    losses = [float(sample_loss(model, s, args).detach().cpu()) for s in samples]
    return float(np.mean(losses)) if losses else math.inf


def train_fold_model(
    train_samples: list[GraphSample],
    val_samples: list[GraphSample],
    input_dim: int,
    args: argparse.Namespace,
    device: torch.device,
) -> tuple[RelationAwareGAT, dict[str, Any]]:
    model = RelationAwareGAT(
        input_dim=input_dim,
        hidden_dim=args.hidden_dim,
        embedding_dim=args.embedding_dim,
        relations=RELATIONS,
        dropout=args.dropout,
    ).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    best_state: dict[str, torch.Tensor] | None = None
    best_val = math.inf
    bad = 0
    history = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        order = np.random.permutation(len(train_samples))
        opt.zero_grad(set_to_none=True)
        batch_loss = 0.0
        batch_count = 0
        epoch_losses = []
        for idx in order:
            loss = sample_loss(model, train_samples[int(idx)], args) / args.batch_dates
            loss.backward()
            batch_loss += float(loss.detach().cpu()) * args.batch_dates
            batch_count += 1
            if batch_count % args.batch_dates == 0:
                nn.utils.clip_grad_norm_(model.parameters(), 2.0)
                opt.step()
                opt.zero_grad(set_to_none=True)
                epoch_losses.append(batch_loss / args.batch_dates)
                batch_loss = 0.0
        if batch_count % args.batch_dates != 0:
            nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            opt.step()
            opt.zero_grad(set_to_none=True)
            rem = batch_count % args.batch_dates
            epoch_losses.append(batch_loss / max(1, rem))

        train_loss = float(np.mean(epoch_losses)) if epoch_losses else math.nan
        val_loss = eval_loss(model, val_samples, args)
        history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss})
        if val_loss < best_val - 1e-6:
            best_val = val_loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            bad = 0
        else:
            bad += 1
            if bad >= args.patience:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    return model, {"best_val_loss": best_val, "epochs_ran": len(history), "history": history}


@torch.no_grad()
def infer_samples(
    model: RelationAwareGAT,
    samples: list[GraphSample],
    stats: FoldStats,
    split: str,
    fold_name: str,
) -> pd.DataFrame:
    model.eval()
    rows = []
    emb_cols = [f"{SUPERVISED_EMB_PREFIX}{i}" for i in range(model.gat2.self_linear.out_features)]
    rel_cols = [f"{SUPERVISED_REL_PREFIX}{rel}" for rel in RELATIONS]
    for sample in samples:
        pred_std, emb, rel_weight = model(sample.x, sample.edges)
        pred = stats.inverse_y(pred_std.detach().cpu().numpy())
        emb_np = emb.detach().cpu().numpy().astype(np.float32)
        rel_np = rel_weight.detach().cpu().numpy().astype(np.float32)
        y = stats.inverse_y(sample.y.detach().cpu().numpy())
        ret = sample.ret.detach().cpu().numpy()
        frame = pd.DataFrame(
            {
                "date": sample.date,
                "symbol": sample.symbols,
                "sector": sample.sectors,
                "split": split,
                "fold": fold_name,
                rmp.EVAL_TARGET_COL: y.astype(np.float32),
                rmp.EVAL_RETURN_COL: ret.astype(np.float32),
                SUPERVISED_SCORE_COL: pred.astype(np.float32),
            }
        )
        for j, col in enumerate(emb_cols):
            frame[col] = emb_np[:, j]
        for j, col in enumerate(rel_cols):
            frame[col] = rel_np[:, j]
        rows.append(frame)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def split_train_internal_val(
    train_dates: pd.DatetimeIndex,
    calendar: pd.DatetimeIndex,
    args: argparse.Namespace,
) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex]:
    if len(train_dates) < 4:
        return train_dates, train_dates
    cutoff = train_dates.max() - pd.DateOffset(years=args.oof_early_stop_years)
    internal_train = train_dates[train_dates <= cutoff]
    internal_val = train_dates[train_dates > cutoff]
    if len(internal_train) == 0 or len(internal_val) == 0:
        n_val = max(1, len(train_dates) // 5)
        internal_train = train_dates[:-n_val]
        internal_val = train_dates[-n_val:]
    if len(internal_train) == 0:
        internal_train = train_dates
    if len(internal_val) == 0:
        internal_val = train_dates[-1:]
    return pd.DatetimeIndex(internal_train), pd.DatetimeIndex(internal_val)


def build_oof_folds(
    train_dates: pd.DatetimeIndex,
    args: argparse.Namespace,
) -> list[tuple[str, pd.Timestamp, pd.Timestamp, pd.DatetimeIndex]]:
    folds = []
    if train_dates.empty:
        return folds
    train_limit = pd.Timestamp(args.train_end)
    fold_train_end = pd.Timestamp(args.first_oof_train_end)
    while fold_train_end < train_limit:
        next_end = fold_train_end + pd.DateOffset(years=args.oof_step_years)
        infer_end = min(next_end, train_limit)
        infer_dates = train_dates[(train_dates > fold_train_end) & (train_dates <= infer_end)]
        if len(infer_dates):
            fold_name = f"oof_train_until_{fold_train_end.date()}_infer_until_{infer_end.date()}"
            folds.append((fold_name, fold_train_end, infer_end, pd.DatetimeIndex(infer_dates)))
        fold_train_end = next_end
    return folds


def summarize_predictions(
    pred: pd.DataFrame,
    horizon_days: int,
    args: argparse.Namespace,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if pred.empty:
        return out
    if args.rebalance_every is None:
        args.rebalance_every = horizon_days
    for split, part in pred.groupby("split", sort=True):
        ic = rmp.spearman_by_date(part, SUPERVISED_SCORE_COL, rmp.EVAL_TARGET_COL, args.min_names_per_date)
        bt = rmp.run_backtest(
            part,
            SUPERVISED_SCORE_COL,
            rmp.EVAL_RETURN_COL,
            args.long_short_pct,
            args.rebalance_every,
            args.transaction_cost_bps,
            args.min_names_per_date,
            args.sector_neutral,
        )
        out[str(split)] = {
            **rmp.summarize_ic(ic, horizon_days),
            **rmp.summarize_backtest(bt, 252.0 / args.rebalance_every),
            "rows": int(len(part)),
            "dates": int(part["date"].nunique()),
        }
    return out


def expand_embeddings_daily(
    graph_embeddings: pd.DataFrame,
    feature_dir: Path,
    out_cols: list[str],
    start_date: str | None,
    end_date: str | None,
) -> pd.DataFrame:
    keys = pd.read_parquet(
        feature_dir / "calendar_metadata.parquet",
        columns=rmp.KEY_COLS + rmp.META_COLS,
    )
    keys["date"] = pd.to_datetime(keys["date"])
    keys["symbol"] = keys["symbol"].astype(str)
    if start_date:
        keys = keys.loc[keys["date"] >= pd.Timestamp(start_date)]
    if end_date:
        keys = keys.loc[keys["date"] <= pd.Timestamp(end_date)]
    emb = graph_embeddings[["date", "symbol", *out_cols]].copy()
    emb["date"] = pd.to_datetime(emb["date"])
    emb["symbol"] = emb["symbol"].astype(str)
    parts = []
    for symbol, key_part in keys.groupby("symbol", sort=False):
        emb_part = emb.loc[emb["symbol"] == symbol].sort_values("date")
        key_part = key_part.sort_values("date")
        if emb_part.empty:
            merged = key_part.copy()
            for col in out_cols:
                merged[col] = np.nan
        else:
            merged = pd.merge_asof(
                key_part,
                emb_part[["date", *out_cols]],
                on="date",
                direction="backward",
                allow_exact_matches=True,
            )
        parts.append(merged)
    return pd.concat(parts, ignore_index=True).sort_values(["date", "symbol"], kind="mergesort")


def write_fold_outputs(run_dir: Path, fold_name: str, pred: pd.DataFrame) -> None:
    fold_dir = run_dir / "folds" / fold_name
    fold_dir.mkdir(parents=True, exist_ok=True)
    pred.to_parquet(fold_dir / "gat_embeddings.parquet", index=False)
    pred[
        [
            "date",
            "symbol",
            "sector",
            "split",
            "fold",
            rmp.EVAL_TARGET_COL,
            rmp.EVAL_RETURN_COL,
            SUPERVISED_SCORE_COL,
        ]
    ].to_parquet(fold_dir / "gat_predictions.parquet", index=False)


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
    if isinstance(value, pd.Timestamp):
        return str(value)
    return value


def main() -> None:
    args = parse_args()
    set_seed(args.seed)
    run_name = args.run_name or now_run_name()
    run_dir = Path(args.out_dir) / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    device = resolve_device(args.device)

    fmap = rmp.read_feature_map(args.feature_map)
    feature_cols = rmp.select_feature_columns(args, fmap)
    edges = load_edges(Path(args.graph_dir))
    graph_dates = edge_dates(edges)
    if args.start_date:
        graph_dates = graph_dates[graph_dates >= pd.Timestamp(args.start_date)]
    if args.end_date:
        graph_dates = graph_dates[graph_dates <= pd.Timestamp(args.end_date)]
    if args.max_graph_dates:
        graph_dates = graph_dates[-args.max_graph_dates :]

    panel, feature_cols, daily_calendar = load_gat_panel(args, graph_dates, feature_cols)
    horizon_days = rmp.infer_horizon_days(args.target_col, args.return_col)
    embargo_days = rmp.resolve_embargo_days(horizon_days, args.embargo_days)
    masks = split_masks(panel, daily_calendar, args.train_end, args.val_end, embargo_days)
    split_dates = {name: date_values(panel, mask) for name, mask in masks.items()}

    print(
        json.dumps(
            {
                "run_name": run_name,
                "device": str(device),
                "target_col": args.target_col,
                "return_col": args.return_col,
                "horizon_days": horizon_days,
                "embargo_days": embargo_days,
                "feature_count": len(feature_cols),
                "graph_dates": int(panel["date"].nunique()),
                "symbols": int(panel["symbol"].nunique()),
                "split_dates": {k: int(len(v)) for k, v in split_dates.items()},
            },
            indent=2,
        ),
        flush=True,
    )

    all_predictions: list[pd.DataFrame] = []
    fold_metrics: dict[str, Any] = {}

    train_dates = split_dates["train"]
    for fold_name, fold_train_end, infer_end, infer_dates in build_oof_folds(train_dates, args):
        fold_train_dates = train_dates[train_dates <= fold_train_end]
        internal_train_dates, internal_val_dates = split_train_internal_val(
            fold_train_dates, daily_calendar, args
        )
        if len(internal_train_dates) == 0 or len(infer_dates) == 0:
            continue
        stats = fit_stats(panel, feature_cols, internal_train_dates)
        train_samples = make_samples(panel, edges, internal_train_dates, stats, device)
        val_samples = make_samples(panel, edges, internal_val_dates, stats, device)
        infer_samples_list = make_samples(panel, edges, infer_dates, stats, device)
        if not train_samples or not infer_samples_list:
            continue
        print(
            f"Training {fold_name}: train_dates={len(internal_train_dates)} "
            f"early_stop_dates={len(internal_val_dates)} infer_dates={len(infer_dates)}",
            flush=True,
        )
        model, info = train_fold_model(train_samples, val_samples, len(feature_cols), args, device)
        pred = infer_samples(model, infer_samples_list, stats, "train_oof", fold_name)
        write_fold_outputs(run_dir, fold_name, pred)
        all_predictions.append(pred)
        fold_metrics[fold_name] = info

    final_train_dates = split_dates["train"]
    final_val_dates = split_dates["val"]
    final_infer_dates = pd.DatetimeIndex(sorted(final_val_dates.union(split_dates["test"])))
    if len(final_train_dates) and len(final_infer_dates):
        stats = fit_stats(panel, feature_cols, final_train_dates)
        train_samples = make_samples(panel, edges, final_train_dates, stats, device)
        val_samples = make_samples(panel, edges, final_val_dates, stats, device)
        infer_samples_list = make_samples(panel, edges, final_infer_dates, stats, device)
        print(
            f"Training final_val_test: train_dates={len(final_train_dates)} "
            f"early_stop_dates={len(final_val_dates)} infer_dates={len(final_infer_dates)}",
            flush=True,
        )
        model, info = train_fold_model(train_samples, val_samples, len(feature_cols), args, device)
        pred = infer_samples(model, infer_samples_list, stats, "val_test", "final_val_test")
        pred.loc[pred["date"].isin(split_dates["val"]), "split"] = "val"
        pred.loc[pred["date"].isin(split_dates["test"]), "split"] = "test"
        write_fold_outputs(run_dir, "final_val_test", pred)
        all_predictions.append(pred)
        fold_metrics["final_val_test"] = info

    if not all_predictions:
        raise RuntimeError("No supervised GAT predictions were generated.")

    graph_pred = pd.concat(all_predictions, ignore_index=True)
    graph_pred = graph_pred.drop_duplicates(["date", "symbol"], keep="last")
    graph_pred = graph_pred.sort_values(["date", "symbol"], kind="mergesort").reset_index(drop=True)

    emb_cols = [f"{SUPERVISED_EMB_PREFIX}{i}" for i in range(args.embedding_dim)]
    rel_cols = [f"{SUPERVISED_REL_PREFIX}{rel}" for rel in RELATIONS]
    out_cols = [SUPERVISED_SCORE_COL, *emb_cols, *rel_cols]
    graph_pred.to_parquet(run_dir / "supervised_gat_graph_date_embeddings.parquet", index=False)
    graph_pred[
        [
            "date",
            "symbol",
            "sector",
            "split",
            "fold",
            rmp.EVAL_TARGET_COL,
            rmp.EVAL_RETURN_COL,
            SUPERVISED_SCORE_COL,
        ]
    ].to_parquet(run_dir / "supervised_gat_graph_date_predictions.parquet", index=False)

    daily = expand_embeddings_daily(
        graph_pred,
        Path(args.feature_dir),
        out_cols,
        args.start_date,
        args.end_date,
    )
    daily.to_parquet(run_dir / "supervised_gat_oof_embeddings.parquet", index=False)

    metrics = {
        "run_name": run_name,
        "target_col": args.target_col,
        "return_col": args.return_col,
        "horizon_days": horizon_days,
        "embargo_days": embargo_days,
        "device": str(device),
        "feature_count": len(feature_cols),
        "graph_date_metrics": summarize_predictions(graph_pred, horizon_days, args),
        "fold_metrics": fold_metrics,
        "split_dates": {k: [str(x.date()) for x in v] for k, v in split_dates.items()},
        "output_columns": out_cols,
    }
    (run_dir / "supervised_gat_metrics.json").write_text(
        json.dumps(clean_json(metrics), indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )
    config = vars(args).copy()
    config["run_name"] = run_name
    config["device_resolved"] = str(device)
    config["feature_count"] = len(feature_cols)
    config["output_columns"] = out_cols
    (run_dir / "config.json").write_text(json.dumps(config, indent=2, default=str), encoding="utf-8")
    pd.DataFrame({"feature": feature_cols}).to_csv(run_dir / "selected_features.csv", index=False)
    print(f"Done. Supervised GAT outputs written to {run_dir}")


if __name__ == "__main__":
    main()
