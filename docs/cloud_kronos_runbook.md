# Cloud Kronos Runbook

This runbook targets either a single 48GB RTX 40-series GPU instance or a
4x24GB RTX 3090 instance.

## 1. Upload And Unpack

On local machine:

```bash
scripts/upload_cloud_bundle.sh dist/research_project_cloud_minimal.tar.gz user@host:/remote/workdir/
```

On cloud:

```bash
cd /remote/workdir
tar -xzf research_project_cloud_minimal.tar.gz
cd research_project
```

## 2. Setup

Use Python 3.10 or 3.11 if available.

```bash
PYTHON_BIN=python3 scripts/setup_cloud_kronos.sh
```

The setup script:

- creates `.venv`
- installs the project/report dependencies
- installs Kronos dependencies
- installs CUDA PyTorch if CUDA torch is not already available
- clones Kronos into `external/Kronos`

If the default PyTorch CUDA wheel index does not match the instance image,
override it:

```bash
PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cu124 scripts/setup_cloud_kronos.sh
```

## 3. Run The Planned Benchmarks

Default plan:

```bash
BATCH_SIZE=256 scripts/run_cloud_kronos_plan.sh
```

This runs:

1. `cloud_small_random_60dates_300`: quick random sampled sanity benchmark.
2. `cloud_small_full`: full Kronos-small zero-shot benchmark.
3. `cloud_base_full`: full Kronos-base zero-shot benchmark.

All prediction jobs are checkpointed by date. If a run stops, repeat the same
command; `--resume` is already included.

For a 4xRTX 3090 instance, run zero-shot as date shards:

```bash
ZERO_SHOT_NUM_GPUS=4 \
BATCH_SIZE=256 \
scripts/run_cloud_kronos_plan.sh
```

This writes per-GPU shard outputs such as
`cloud_small_full_shard0_of4/` and then merges them into the normal final output
directory, for example `cloud_small_full/`. Use the merged directory for final
IC and report comparison.

Outputs are written under:

```text
output/kronos_zero_shot/<run-name>/
```

Important files:

```text
predictions.parquet
metrics.csv
comparison_to_report.csv
rank_ic_by_date.csv
summary.md
```

## 4. Optional Predictor Fine-Tune

After the zero-shot benchmarks, run predictor-only fine-tuning:

```bash
RUN_SMALL_FULL=0 \
RUN_BASE_FULL=0 \
RUN_PREDICTOR_FINETUNE=1 \
FINETUNE_EPOCHS=3 \
FINETUNE_BATCH_SIZE=64 \
scripts/run_cloud_kronos_plan.sh
```

On a 4xRTX 3090 instance, use Kronos DDP and lower the per-GPU batch size if
needed:

```bash
RUN_SMALL_FULL=0 \
RUN_BASE_FULL=0 \
RUN_PREDICTOR_FINETUNE=1 \
FINETUNE_NUM_GPUS=4 \
FINETUNE_EPOCHS=3 \
FINETUNE_BATCH_SIZE=32 \
scripts/run_cloud_kronos_plan.sh
```

This prepares:

```text
data/kronos/sp500_daily/train_data.pkl
data/kronos/sp500_daily/val_data.pkl
data/kronos/sp500_daily/test_data.pkl
```

Then it fine-tunes the Kronos predictor from `NeoQuasar/Kronos-small` while
using the pretrained tokenizer.

Fine-tuned model output:

```text
output/kronos_finetune/predictor_sp500/checkpoints/best_model/
```

## 5. Optional Tokenizer Fine-Tune

Tokenizer fine-tuning is more invasive and should run only after predictor-only
fine-tuning has been evaluated:

```bash
RUN_SMALL_FULL=0 \
RUN_BASE_FULL=0 \
RUN_TOKENIZER_FINETUNE=1 \
RUN_PREDICTOR_FINETUNE=1 \
FINETUNE_EPOCHS=3 \
FINETUNE_BATCH_SIZE=64 \
scripts/run_cloud_kronos_plan.sh
```

## 6. Pull Results Back

From local machine:

```bash
rsync -av user@host:/remote/workdir/research_project/output/kronos_zero_shot/ output/kronos_zero_shot_cloud/
rsync -av user@host:/remote/workdir/research_project/output/kronos_finetune/ output/kronos_finetune_cloud/
```

## 7. Practical Notes

- Start with `BATCH_SIZE=256`; with 48GB GPU you can try `512` or `768`.
- On 4xRTX 3090, `BATCH_SIZE=256` is per shard process. If Kronos-base OOMs on
  a 24GB card, retry with `BATCH_SIZE=128`.
- Keep `--resume`; full zero-shot is long and date-level checkpointing prevents wasted work.
- The current local sampled benchmark showed Kronos-small zero-shot was not stable on test IC. The cloud run should confirm this at full scale and then test whether Kronos-base or fine-tuning changes the conclusion.
