# Graph Relation Features

This module adds true sparse graph relations and graph relation embeddings on top of the tabular feature groups.

## Outputs

Graph edge files:

```text
data/processed/graphs/
  graph_node_features.parquet
  sector_edges.parquet
  style_knn_edges.parquet
  rolling_corr_edges.parquet
  graph_edge_metadata.json
```

Graph embedding files:

```text
data/processed/graph_embeddings/
  graph_relation_embeddings_rebalance.parquet
  graph_relation_embeddings_daily.parquet
  graph_embedding_manifest.csv
  graph_embedding_metadata.json
```

Audit:

```text
data/processed/graph_feature_audit.json
```

## Relation Types

### Sector Graph

`sector_edges.parquet` connects each stock to same-sector and same-sub-industry peers. Neighbors are capped at top-k per stock-date and selected by nearest distance in the style feature space. Same sub-industry receives higher base weight than same broad sector.

### Style kNN Graph

`style_knn_edges.parquet` connects each stock to the nearest stocks in a cross-sectional feature space built from momentum, volatility, liquidity, RSI, trend, and dollar-volume features. This is the no-external-data proxy for Barra-style similarity.

### Rolling Correlation Graph

`rolling_corr_edges.parquet` connects each stock to stocks with high trailing return correlation. The current default uses a 60-trading-day window and keeps the top 10 positive correlations above the configured threshold.

## Edge Convention

Edges use this convention:

```text
src = target stock receiving information
dst = neighbor stock sending information
```

So for one row `src=AAPL, dst=MSFT`, the embedding for AAPL can attend to MSFT.

## Rebalance Frequency

Graphs are rebuilt every 20 trading days after the first 252 trading days. This keeps edge files compact and avoids unstable early history. Daily graph embeddings are forward-filled from the latest rebalance date.

Rows before the first rebalance date have missing graph embeddings; this is expected and should be dropped or imputed during modeling.

## Graph Relation Embeddings

`graph_relation_embeddings_daily.parquet` contains:

- `graph_emb_0` ... `graph_emb_15`
- `graph_rel_weight_sector`
- `graph_rel_weight_style_knn`
- `graph_rel_weight_rolling_corr`

The three `graph_rel_weight_*` values are normalized across relation types and
usually sum to about 1 up to floating-point error. For each stock-date they show
whether the graph relation embedding relies more on sector peers, style-nearest
peers, or rolling-correlation peers.

The encoder is a deterministic two-layer graph relation encoder:

1. Relation-internal aggregation summarizes neighbors separately for sector, style kNN, and rolling correlation edges.
2. Relation-level fusion combines the three relation embeddings into one stock embedding.
3. The model does not use forward returns or target labels, so the produced embedding is a no-lookahead graph feature.

Important distinction: this is a dependency-light graph relation feature encoder, not a supervised graph neural network trained end-to-end on future returns. It is appropriate as a robust graph feature baseline for LGBM/XGBoost.

## Usage

The runnable model pipeline can include graph embeddings directly:

```bash
python scripts/run_model_pipeline.py \
  --run-name ridge_core_graph_5d \
  --feature-set core \
  --include-graph-embeddings
```

The canonical walk-forward grid treats graph inclusion as a formal feature
variant. By default it runs both `tabular` and `graph`; set `FEATURE_VARIANTS`
to limit the axis:

```bash
scripts/run_walk_forward_grid.sh
FEATURE_VARIANTS="graph" scripts/run_walk_forward_grid.sh
```

Manual joins are still possible. Join graph embeddings with any feature group on
`date, symbol`:

```python
from pathlib import Path
import pandas as pd

feature_dir = Path("/Users/jackiewang/Documents/research project/data/processed/features_by_group")
graph_dir = Path("/Users/jackiewang/Documents/research project/data/processed/graph_embeddings")

base = pd.read_parquet(feature_dir / "cross_sectional.parquet")
target = pd.read_parquet(
    feature_dir / "targets.parquet",
    columns=["date", "symbol", "target_excess_market_fwd_5d"],
)
graph = pd.read_parquet(graph_dir / "graph_relation_embeddings_daily.parquet")

df = (
    base
    .merge(graph, on=["date", "symbol", "sector", "sub_industry", "hq_state", "hq_region"], how="left")
    .merge(target, on=["date", "symbol"], how="left")
)

graph_cols = [c for c in df.columns if c.startswith("graph_emb_") or c.startswith("graph_rel_weight_")]
df = df.dropna(subset=graph_cols + ["target_excess_market_fwd_5d"])

X = df.drop(columns=["target_excess_market_fwd_5d"])
y = df["target_excess_market_fwd_5d"]
```

## Rebuild Commands

```bash
python scripts/build_graph_edges.py
python scripts/make_graph_embeddings.py
```

`make_graph_embeddings.py` also writes `data/processed/graph_feature_audit.json`
so the edge metadata, embedding metadata, missing-embedding counts, and
relation-weight checks stay synchronized with the current feature panel.
