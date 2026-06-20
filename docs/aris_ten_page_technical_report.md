# A Reproducible S&P 500 Forecasting Pipeline: First ARIS Technical-Report Draft

## 1. Executive Summary

This repository implements a reproducible research workflow for daily
cross-sectional prediction on a large-cap U.S. equity universe derived from S&P
500 data. The current project is best understood as an engineering and
methodology report rather than a finished alpha paper. Its strongest claims are
about pipeline design, leakage controls, feature coverage, and reproducible
execution. Its weaker claims are about final economic performance, because the
cloud copy does not yet contain a complete, committed archive of full
model-pipeline experiment outputs across all target families and horizons.

The workflow starts from daily OHLCV data plus static company metadata, builds
grouped stock-date features, defines forward-return targets over multiple
horizons, and evaluates cross-sectional prediction with ranking metrics and a
long-short decile backtest. The default runnable configuration predicts
`target_excess_sector_fwd_5d`, uses `target_ret_fwd_5d` for realized portfolio
PnL, trains a ridge model on a curated `core` feature set, and compares that
model with a simple momentum-rank baseline. Optional paths extend the workflow
to LightGBM, XGBoost, scikit-learn HGB, graph embeddings, and Kronos zero-shot
or fine-tuned sequence models.

The main methodological contribution already present in code is the hardening of
temporal validation. The current pipeline enforces a one-trading-day execution
lag, purges rows whose forward labels cross split boundaries, and applies a
horizon-based embargo at the start of validation and test blocks. Those changes
close several major leakage channels identified in the project review:
cross-boundary label contamination, same-close execution assumptions, and
boundary adjacency effects in highly autocorrelated financial features. A
lightweight synthetic validation of these mechanics is archived in
`review-stage/20260620-1324-leakage-validation.md`; production claims still
require fresh full-data runs and their split-audit outputs.

The most important unresolved limitation is survivorship bias. The dataset is
constructed from current or recent S&P 500 constituents rather than a strict
point-in-time historical index membership file with delisting treatment. That
means the project can support statements such as "predictive ranking behavior on
historical prices of current or recent S&P 500 constituents," but it cannot yet
support strong claims about a fully tradable historical S&P 500 backtest.

As of this cloud run, the strongest directly inspectable result artifacts are
Kronos zero-shot benchmark summaries present in the cloud working copy under
`output/kronos_zero_shot/`. Because `output/` is an untracked experiment-output
area, those summaries are local evidence rather than versioned repository
evidence. They show that small-sample Kronos runs can look strong, but the
larger random 60-date benchmark is unstable: validation ICs are mildly positive
while test ICs are negative across 1D, 5D, and 20D horizons. That is not
sufficient evidence to claim robust sequence-model alpha. The correct current
conclusion is that the workflow is credible and useful for controlled
experimentation, but the final empirical story remains provisional and needs a
fresh full baseline-and-target-model rerun before paper-level claims are made.

## 2. Research Objective and Market Prediction Setup

The research problem is not raw index forecasting. It is daily
cross-sectional equity ranking: given information available on stock-date
\(i, t\), can the workflow assign a score that is useful for ranking large-cap
stocks by future relative performance over a fixed horizon? This distinction is
important because most portfolio construction decisions in equity statistical
arbitrage are relative rather than directional. The portfolio does not need to
predict the market level correctly; it needs to sort names well enough for a
long-short selection rule to monetize the spread between stronger and weaker
stocks.

That framing drives several design choices in the repository:

- The default target is sector-relative forward return,
  `target_excess_sector_fwd_5d`, rather than raw return.
- The main evaluation metric is rank IC rather than regression RMSE.
- The backtest forms top-decile long and bottom-decile short portfolios, with
  optional sector-neutral construction.

Each modeling row is one stock-date observation. Features are built at the
stock-date level, often with rolling windows over past returns, volatility, or
volume, and may also include cross-sectional transforms computed within a date,
sector, or sub-industry bucket. Targets are forward returns at horizons from 1
to 150 trading days. The default runnable pipeline uses a 5-day horizon, a
one-day execution lag, and a 5-trading-day rebalance schedule. That combination
is a pragmatic medium-frequency research setup: slow enough to move beyond
microstructure noise, but short enough to preserve a meaningful number of
cross-sections and training examples.

The default chronological design in `scripts/run_model_pipeline.py` is:

- Start date: `2005-01-01`
- Train end: `2018-12-31`
- Validation end: `2020-12-31`
- Test: dates after `2020-12-31`

This is a simple anchored split rather than a fully expanding walk-forward
scheme. The repository documentation explicitly argues that expanding
walk-forward validation is the preferred long-run design, but the main runnable
pipeline currently uses the anchored split as its operational baseline. That is
acceptable for a first technical report as long as the report is careful not to
overstate the robustness of any single validation block.

The economic intuition for the setup is also straightforward. Relative equity
prediction is more defensible than raw return prediction because common market
beta dominates short-horizon raw returns. By de-meaning relative to the market
or sector and optimizing a cross-sectional ranking objective, the workflow aims
to isolate weaker but more stable stock-specific structure: momentum spillovers,
volatility state, crowding, liquidity pressure, technical trend continuation or
reversal, and peer-group divergence.

## 3. Data Sources and Reproducibility Boundary

The repository is intentionally narrow in both data scope and reproducibility
scope. The raw research data comes from two principal files:

- `data/raw/sp500_stocks.csv`
- `data/raw/sp500_companies.csv`

The stock file provides daily OHLCV plus ticker. The company file provides
sector, sub-industry, headquarters, `date_added`, and `founded` metadata. The
feature catalog states clearly that the current workflow does not use external
fundamentals, market capitalization, analyst data, supply-chain relations,
macroeconomic releases, or point-in-time alternative datasets. That restriction
is deliberate. It keeps the workflow reproducible in a lightweight cloud clone
and makes the leakage review easier because every feature must ultimately be
traceable back to included price-volume series and bundled metadata.

The repository also defines a clear Git boundary:

- Tracked: `scripts/`, `docs/`, `requirements.txt`, lightweight vendored code,
  and small report assets.
- Not tracked: raw/interim/processed datasets under `data/`, generated
  experiment outputs under `output/`, cloud bundles under `dist/`, temporary
  files under `tmp/`, and local credentials.

That boundary matters for interpreting this report. Reproducibility here means
that the code path, documentation, and command sequence are versioned and can be
re-executed. It does not mean that all raw data and all experiment results are
checked into Git. In this cloud copy, some outputs exist locally, including
Kronos zero-shot summaries, but they sit under the untracked `output/` boundary.
There is no fully committed archive of all baseline model runs that would
support a finished quantitative paper.

The intended rebuild path is explicit:

```bash
bash scripts/run_cloud_data_pipeline.sh
```

For a smoke test:

```bash
PIPELINE_MODE=smoke bash scripts/run_cloud_data_pipeline.sh
```

That command-level explicitness is one of the better features of the project.
The repository does not ask a future reader to reconstruct hidden notebook
state, ad hoc preprocessing, or undocumented environment steps. A new machine
should be able to move from raw bundle reconstruction to typed interim files,
then to grouped features, graph edges, graph embeddings, and finally diagnostic
or modeling scripts through a visible script chain. For a technical report, that
is valuable in its own right: even before the final alpha claim is settled, the
workflow already demonstrates a reproducible experimental scaffold that another
researcher could extend.

At the feature level, the workflow prepares typed Parquet files and then writes
grouped feature outputs under `data/processed/features_by_group/`. Grouped
output is important for reproducibility and scale. Instead of relying on one
very wide monolithic table, the project stores feature families independently
and lets downstream modeling join only the required groups. This reduces memory
pressure and makes feature provenance easier to audit.

There is also a practical reproducibility boundary around the cloud Kronos path.
The runbook documents a deterministic setup sequence, explicit environment
choices, and where outputs should be written under
`output/kronos_zero_shot/` and `output/kronos_finetune/`. That path is
reproducible as an operational procedure, even if the final GPU-generated
artifacts are not committed to the repository by default.

## 4. Feature Engineering, Including Technical, Graph, and Regime Features

The feature pipeline is broad for a no-external-data project. It spans ten
grouped Parquet outputs and several hundred columns, organized around technical,
cross-sectional, industry, liquidity, metadata, and target families. The
feature catalog reports the following group sizes in the current full build:

| Group file | Columns |
|---|---:|
| `calendar_metadata.parquet` | 23 |
| `price_momentum.parquet` | 50 |
| `volatility.parquet` | 69 |
| `trend_technical.parquet` | 56 |
| `liquidity_volume.parquet` | 41 |
| `market_industry.parquet` | 52 |
| `statistical_linkage.parquet` | 8 |
| `peer_style_geography.parquet` | 58 |
| `cross_sectional.parquet` | 168 |
| `targets.parquet` | 48 |

The technical feature families cover standard daily systematic-equity signals:

- Multi-window returns, skip-window momentum, reversal, and momentum
  acceleration.
- Volatility, downside risk, drawdown, Parkinson and Garman-Klass estimators,
  skew, kurtosis, and tail descriptors.
- SMA and EMA gaps, slopes, MACD, RSI, Bollinger position and bandwidth,
  channel position, breakout distance, Williams %R, and similar trend/technical
  indicators.
- Liquidity and activity measures such as log volume, dollar volume,
  volume z-scores, volume momentum, and Amihud-style illiquidity.

These are not exotic features, but that is a strength for a first report. They
are interpretable, easy to audit, and aligned with how cross-sectional equity
signals are usually prototyped.

The project also includes regime and contextual features. Those include
equal-weight market return, market volatility, breadth, cross-sectional
dispersion, market dollar volume, sector and sub-industry rolling behavior, and
stock excess returns relative to sector or sub-industry peers. This is the
repository’s built-in answer to regime dependence: instead of assuming a
momentum or mean-reversion signal is stable everywhere, the feature space gives
the model enough state information to learn that a signal can behave
differently in high-volatility, low-breadth, or dispersion-heavy periods.

Another important layer is cross-sectional transformation. Many raw signals are
re-expressed as:

- date-wise cross-sectional ranks or z-scores,
- sector-neutral ranks or z-scores,
- sub-industry-neutral ranks or z-scores.

That is methodologically consistent with the project objective. If the target is
relative future performance, then normalized cross-sectional transforms are
often more informative than raw levels.

The feature set also uses peer, style, and geography context built only from the
included metadata. Leave-one-out peer means, peer excess values within sector or
sub-industry, headquarters-state and headquarters-region peer returns, and
coarse style buckets are used as low-cost proxies for exposure structure that a
fully institutional model might derive from richer vendor datasets.

Graph features are the most distinctive extension. The repository adds:

- sector/sub-industry graph edges,
- style k-nearest-neighbor edges,
- rolling-correlation edges,
- deterministic relation-aware graph embeddings.

The edge convention is directional: `src` is the stock receiving information and
`dst` is the neighbor sending information. Graphs are rebuilt every 20 trading
days after the first 252 trading days, which provides a warm-up period before
graph construction becomes stable. Daily graph embeddings are then forward-filled
from the latest rebalance date. Rows before the first rebalance naturally have
missing graph embeddings and must be dropped or imputed in downstream modeling.

The graph encoder is intentionally conservative. It is a deterministic,
dependency-light, GAT-style feature encoder rather than a fully supervised
end-to-end graph neural network trained on forward returns. That matters for
leakage control: the graph embedding is designed as a no-lookahead feature
transform, not a label-trained sequence model that would require its own
carefully split training loop.

The default `core` modeling set in `run_model_pipeline.py` is narrower than the
full catalog. It selects a curated subset of momentum, volatility, drawdown,
technical, liquidity, market, industry, peer, beta, and normalized features.
This is a sensible default for a reproducible benchmark because it reduces
dimensionality and keeps the first-pass model path fast and inspectable. The
`all` option and explicit `--feature-groups` path remain available for broader
experiments.

## 5. Labeling, Horizon Alignment, and Leakage Controls

Label construction is where this project became materially stronger after the
leakage review. The feature generator creates several forward-return target
families across horizons:

- `target_ret_fwd_{h}d`
- `target_excess_market_fwd_{h}d`
- `target_excess_sector_fwd_{h}d`
- `target_rank_fwd_{h}d`

with \(h \in \{1, 5, 20, 30, 40, 50, 60, 70, 80, 90, 120, 150\}\).

The forward-return logic is standard in concept but dangerous at split
boundaries. A row dated \(t\) uses future price information out to \(t+h\).
Without extra controls, the last rows of a training block will silently use
future validation-period prices to define their labels, and long horizons make
that contamination non-trivial. The leakage review quantified this problem and
showed that for long horizons such as 60D or 120D, a meaningful fraction of
training rows can have labels that extend into the next split.

The current main pipeline fixes this by explicitly constructing:

- an effective evaluation target shifted by execution lag,
- an effective realized return shifted by execution lag,
- a per-row `_label_end_date`.

For the default `--execution-lag-days 1`, a signal formed from features on date
\(t\) is evaluated against future returns beginning on \(t+1\), not the same
close. This is a crucial realism improvement because many features use closing
price, intraday range, and full-day volume. Evaluating those signals against a
same-close trade assumes knowledge and execution that are not realistically
available.

The main rules now implemented are:

1. Training rows are kept only if `_label_end_date <= train_end`.
2. Validation rows are kept only if `_label_end_date <= val_end`.
3. Validation and test starts are embargoed by a configurable number of trading
   days, which defaults to the target horizon.

These controls address different leakage channels:

- Purge addresses label overlap across split boundaries.
- Execution lag addresses same-close or same-bar execution bias.
- Embargo addresses serial dependence near the start of future blocks.

This combination is stronger than the simplistic "time split only" pattern that
appears in many ML-for-finance prototypes. It still does not guarantee perfect
realism, but it closes the highest-risk look-ahead paths identified in the repo
review. The lightweight validation artifact
`review-stage/20260620-1324-leakage-validation.md` checks horizon mismatch
errors, execution-lagged labels, boundary purge, and embargo behavior on a
synthetic panel.

The reporting discipline is also improved. The pipeline writes a split audit and
explicitly records `label_end_max` for each split. For a clean run, the audit
must show that:

- `train.label_end_max` is no later than `train-end`,
- `val.label_end_max` is no later than `val-end`.

That is exactly the kind of machine-generated evidence a reproducibility-focused
technical report should emphasize.

## 6. Model Pipeline and Evaluation Protocol

The modeling pipeline in `scripts/run_model_pipeline.py` is designed as an
end-to-end, dependency-light research harness. It loads the target panel,
selectively joins feature groups, optionally merges graph embeddings, attaches
effective labels, applies split logic, fits a preprocessor on training rows
only, trains a model, scores validation and test rows, and writes both numeric
artifacts and a report-friendly summary.

The default baseline is deliberately simple: a single cross-sectional momentum
rank feature. The default model is ridge regression implemented in NumPy, which
means the baseline runnable pipeline works without assuming scikit-learn,
LightGBM, or XGBoost are installed. This is a practical reproducibility choice.
It ensures that the repository still has a deterministic and low-friction
benchmark even in minimal environments.

At the same time, the script supports stronger nonlinear alternatives:

- `lightgbm`
- `xgboost`
- `sklearn-hgb`
- `auto`, which chooses the strongest installed backend in a fixed order

The evaluation protocol is aligned with the research objective:

- Rank IC by date measures cross-sectional predictive monotonicity.
- ICIR annualizes the mean-over-volatility of rank IC.
- Decile spread measures average top-minus-bottom target separation.
- A long-short backtest converts scores into realized gross and net returns.
- Transaction costs are modeled through turnover times configured one-way bps.

The portfolio constructor is also explicit. For the non-sector-neutral case, it
takes the top and bottom deciles, assigns 0.5 gross weight to the long side and
0.5 gross weight to the short side, and rebalances every configured number of
trading days. The sector-neutral variant repeats this inside sector groups and
averages across usable sectors. That is not a production portfolio optimizer,
but it is transparent and sufficient for model-comparison research.

The repository also includes a higher-level experiment runner,
`scripts/run_target_model_experiments.py`, which sweeps:

- target families,
- horizons,
- model classes,
- model-specific hyperparameter grids.

Importantly, that runner now inherits the execution lag and optional embargo
settings from the main pipeline. That means comparative model experiments are no
longer silently using a less realistic labeling protocol than the documented
default.

The output contract of the main pipeline is also report-friendly. Each run can
write:

- `summary.md` for quick human inspection,
- `metrics.json` for machine-readable aggregation,
- `selected_features.csv` and `feature_importance.csv` for model interpretation,
- per-split rank-IC, decile-spread, and backtest CSVs,
- optional `predictions_val_test.parquet` for deeper audit work.

This matters because a technical-report workflow should not rely on one final
figure export as the only surviving artifact. The repository is set up so that a
future paper pass can regenerate tables from structured outputs rather than
retyping numbers into prose.

From a report-design perspective, the right interpretation of this stack is:
the repository already supports reproducible benchmark generation and structured
model comparisons, but the current cloud copy is missing a fresh committed batch
of those outputs. The architecture is in place; the empirical archive is not yet
complete enough to be a final paper table.

## 7. Walk-Forward Validation with Purge and Embargo

The repository documentation correctly argues that expanding walk-forward
validation should be the preferred long-run research design. The rationale is
strong: financial data are non-stationary, a single validation block can be
regime-specific, and iterative retraining on expanding history is closer to
actual deployment than one fixed historical split.

The walk-forward documents recommend a structure like:

- Train on a historical window.
- Validate on the next future block.
- Test on the next unseen block.
- Expand the training window.
- Repeat across multiple folds.

They also correctly place purge between train and validation, and embargo after
validation before future trainable data is allowed back into later folds. This
matches the López de Prado style logic that is now standard for finance-aware
cross-validation.

However, it is important to separate documented best practice from current code
default. The main runnable pipeline does not yet implement a full multi-fold
expanding walk-forward loop. It implements a single anchored train/validation/
test split with per-row purge and start-of-block embargo. That is a meaningful
improvement over naive chronology, but it is still not the same as evaluating
model selection stability across repeated future blocks.

This distinction should appear plainly in a technical report because it affects
what claims are justified:

- It is justified to claim that the current code enforces purge and embargo on
  its anchored split.
- It is not yet justified to claim that the project’s core reported numbers are
  based on a full expanding walk-forward evaluation, unless a separate wrapper
  is added and executed.

The correct report framing is therefore:

1. The current baseline pipeline uses a fixed chronological split hardened with
   purge, embargo, and execution lag.
2. The repository’s recommended next validation upgrade is an expanding
   walk-forward framework plus a final untouched hold-out block.
3. Any strong statement about robustness across market regimes should wait for
   that upgrade.

This is not a weakness in the report. It is exactly the kind of honest
methodological scoping that prevents accidental overclaiming.

## 8. Current Experimental Results and What Is Still Provisional

The most important fact about the current cloud copy is that its experiment
archive is incomplete. There are no tracked `output/model_pipeline/...`
artifacts in this worktree for the classical ridge/LightGBM/XGBoost runs that
the scripts are designed to produce. That means this report cannot responsibly
present a polished "main table" for the tabular models based only on
documentation.

What does exist locally are several Kronos zero-shot summaries under
`output/kronos_zero_shot/`. Those untracked artifacts are informative, but they
are not enough to close the full empirical story unless lightweight summaries
are copied into a tracked report-artifacts path.
All Kronos numbers below should therefore be read as local-only illustrative
evidence from this cloud working copy, not as part of the Git-reproducible
repository record.

The clearest local Kronos result is the 60-date random 300-symbol benchmark in
`output/kronos_zero_shot/kronos_random_60dates_300/summary.md`. Its pattern is
not encouraging:

- 1D validation mean rank IC is positive at about 0.041, but 1D test mean rank
  IC is negative at about -0.007.
- 5D validation mean rank IC is positive at about 0.018, but 5D test mean rank
  IC is negative at about -0.022.
- 20D validation mean rank IC is near zero, and 20D test mean rank IC is
  negative at about -0.015.

The corresponding ICIR comparisons in the same summary show the local Kronos
test results lagging the report-referenced best baseline models by a wide margin
on that larger random sample. The correct interpretation is that Kronos-small
zero-shot is not yet a reliable winner in this dataset setting.

There are also smaller local benchmarks, such as
`sampled_10dates_120/summary.md`, where Kronos looks strong on test slices.
Those runs are too small and too unstable to treat as load-bearing evidence:

- the date count is tiny,
- validation and test signs can flip,
- the sample is susceptible to luck and regime concentration,
- extremely high ICIR values on a handful of dates are not paper-grade
  stability evidence.

So the current empirical status is:

- The infrastructure for baseline tabular experiments exists.
- The infrastructure for target-family and horizon sweeps exists.
- The infrastructure for cloud Kronos runs exists.
- The local cloud artifacts are sufficient to show that some sequence-model
  results are unstable and still provisional.
- The local cloud artifacts are not sufficient to make a robust "best model"
  claim for the project.

If the classical tabular runs are regenerated, the report should present them in
two layers. The first layer should be a validation-selection table keyed on
validation ICIR only, because the leakage review explicitly warns against using
test results to choose winners. The second layer should be a frozen out-of-sample
test table showing rank IC, ICIR, top-bottom spread, annualized net return,
annualized volatility, Sharpe, drawdown, and turnover for the chosen models.
That would align the final report structure with the logic already encoded in
the scripts instead of retrofitting a narrative after the fact.

This is why the technical report should focus its strongest claims on workflow
quality rather than alpha magnitude. The pipeline already demonstrates:

- explicit feature provenance,
- no-external-data modeling paths,
- grouped feature materialization,
- leakage-aware label handling,
- reproducible command paths for cloud GPU experiments.

What remains provisional are the final performance comparisons, especially:

- tabular baseline leaderboard values,
- horizon-generalization conclusions,
- graph-feature uplift estimates,
- Kronos zero-shot versus fine-tuned conclusions,
- any claim about deployable long-short profitability after realistic frictions.

## 9. Limitations, Risk Controls, and Failure Modes

The first limitation is survivorship bias, and it is a major one. The current
dataset appears to represent the historical prices of current or recent S&P 500
constituents rather than a strict point-in-time universe that includes delisted,
acquired, and removed companies with appropriate treatment. That means:

- long-only or long-short backtests can be overly optimistic,
- tail risk can be understated,
- failed-company patterns are underrepresented,
- the results should not be presented as a true historical S&P 500 tradable
  backtest.

The second limitation is validation depth. The main code path is still an
anchored split, not a repeated walk-forward evaluation. Even with purge and
embargo, a single validation era can still lead to brittle model selection.

The third limitation is result completeness. The cloud copy used for this run
does not include a fresh committed output set for the core tabular experiments.
That makes the report strong on system description and weak on final
quantitative synthesis.

The fourth limitation is feature realism. This is a no-external-data workflow by
design. That is excellent for reproducibility, but it also means the model does
not yet benefit from richer point-in-time fundamentals, market-cap data,
corporate actions processing beyond what is bundled, or professional universe
construction datasets.

The fifth limitation is graph maturity. The graph embeddings are careful and
no-lookahead, but they are still an unsupervised feature layer rather than a
fully trained graph model. The research question "do graph relations improve
out-of-sample ranking?" is therefore still open.

The sixth limitation is an implementation detail noted in the leakage review:
when `--max-train-rows` is used, training rows are randomly sampled within the
training split rather than uniformly by date. That does not leak future data,
but it can distort the date distribution of the preprocessor fit and slightly
change the cross-sectional composition of the training set.

The seventh limitation is review coverage. For this run, the repository’s
Copilot Opus review gate could be prepared locally, but the actual external
read-only reviewer was not callable from this noninteractive cloud environment.
That does not invalidate the report draft, but it does mean the final artifact
still needs an independent reviewer pass before it should be treated as frozen.

The project already contains several risk controls that should remain central to
future report versions:

- execution lag to prevent same-close assumptions,
- per-row purge and split audits,
- horizon-based embargo,
- explicit transaction-cost accounting,
- sector-neutral portfolio option,
- grouped-feature design that makes provenance and ablation easier,
- clear documentation of what is reproducible and what is excluded from Git.

## 10. Next Experiments and Paper-Writing Roadmap

The immediate next step is not aesthetic polishing. It is evidence completion.
Before converting this into a submission-style paper, the project should produce
and archive a fresh baseline experiment pack for the tabular models. At minimum,
that pack should include:

- a default ridge `core` run,
- LightGBM and XGBoost comparisons on the same clean split,
- horizon sweeps for 1D, 5D, 20D, and selected longer horizons,
- graph-embedding inclusion versus exclusion,
- sector-neutral versus non-sector-neutral portfolio construction where useful.

The second priority is validation hardening. The documented walk-forward
framework should be promoted from methodology note to executable experiment
driver. Once that exists, model-selection decisions can be reported across
multiple future blocks rather than one anchored validation period.

The third priority is universe realism. If the project aims to make stronger
trading claims, it needs point-in-time universe membership, delisting treatment,
and clearer historical corporate-action coverage. Without that, the right final
product remains a reproducible engineering report rather than an investment
strategy paper.

The fourth priority is Kronos clarification. The cloud runbook is already good
enough to support disciplined GPU experiments. What is needed now is a coherent
comparison set:

- Kronos-small zero-shot,
- Kronos-base zero-shot,
- predictor-only fine-tuning,
- possibly tokenizer fine-tuning only after predictor-only evidence justifies it.

Those runs should be judged on the same leakage-clean targets and the same
evaluation protocol as the tabular baselines.

The fifth priority is ARIS packaging. For a formal paper-writing path, the next
document chain should be:

1. this Markdown report as the narrative technical baseline,
2. a tighter `NARRATIVE_REPORT.md` with claim/evidence structure,
3. a `PAPER_PLAN.md` with section, figure, and table plan,
4. figure generation and result table freezing,
5. a paper-writing pass only after the evidence base is complete.

In short, the current repository is ready for a serious technical report draft,
ready for disciplined reruns, and not yet ready for strong publishable empirical
claims. That is a productive place to be. The methodology is substantially more
credible now that purge, embargo, and execution lag are explicit in code. The
next phase is to generate the missing experiment archive and let the final paper
be evidence-led rather than documentation-led.
