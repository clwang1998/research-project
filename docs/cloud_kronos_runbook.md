# Cloud Kronos Runbook

This runbook targets a single 48GB RTX 40-series GPU instance.

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
- Keep `--resume`; full zero-shot is long and date-level checkpointing prevents wasted work.
- The current local sampled benchmark showed Kronos-small zero-shot was not stable on test IC. The cloud run should confirm this at full scale and then test whether Kronos-base or fine-tuning changes the conclusion.
