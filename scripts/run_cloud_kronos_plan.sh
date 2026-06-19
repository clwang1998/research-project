#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

VENV_DIR="${VENV_DIR:-.venv}"
KRONOS_ROOT="${KRONOS_ROOT:-external/Kronos}"
DEVICE="${DEVICE:-cuda:0}"
BATCH_SIZE="${BATCH_SIZE:-256}"
SMOKE_BATCH_SIZE="${SMOKE_BATCH_SIZE:-128}"
RUN_PREFIX="${RUN_PREFIX:-cloud}"
RUN_SMOKE_SAMPLE="${RUN_SMOKE_SAMPLE:-1}"
RUN_SMALL_FULL="${RUN_SMALL_FULL:-1}"
RUN_BASE_FULL="${RUN_BASE_FULL:-1}"
RUN_PREDICTOR_FINETUNE="${RUN_PREDICTOR_FINETUNE:-0}"
RUN_TOKENIZER_FINETUNE="${RUN_TOKENIZER_FINETUNE:-0}"
FINETUNE_EPOCHS="${FINETUNE_EPOCHS:-3}"
FINETUNE_BATCH_SIZE="${FINETUNE_BATCH_SIZE:-64}"

source "$VENV_DIR/bin/activate"

if [[ "$RUN_SMOKE_SAMPLE" == "1" ]]; then
  echo "== Kronos smoke sample =="
  python scripts/run_kronos_zero_shot.py \
    --run-name "${RUN_PREFIX}_small_random_60dates_300" \
    --date-stride 30 \
    --max-dates 60 \
    --max-symbols 300 \
    --symbol-sample random \
    --batch-size "$SMOKE_BATCH_SIZE" \
    --min-names-per-date 100 \
    --device "$DEVICE" \
    --kronos-root "$KRONOS_ROOT" \
    --resume
fi

if [[ "$RUN_SMALL_FULL" == "1" ]]; then
  echo "== Kronos-small full zero-shot =="
  python scripts/run_kronos_zero_shot.py \
    --run-name "${RUN_PREFIX}_small_full" \
    --batch-size "$BATCH_SIZE" \
    --min-names-per-date 100 \
    --device "$DEVICE" \
    --kronos-root "$KRONOS_ROOT" \
    --model-id NeoQuasar/Kronos-small \
    --tokenizer-id NeoQuasar/Kronos-Tokenizer-base \
    --resume
fi

if [[ "$RUN_BASE_FULL" == "1" ]]; then
  echo "== Kronos-base full zero-shot =="
  python scripts/run_kronos_zero_shot.py \
    --run-name "${RUN_PREFIX}_base_full" \
    --batch-size "$BATCH_SIZE" \
    --min-names-per-date 100 \
    --device "$DEVICE" \
    --kronos-root "$KRONOS_ROOT" \
    --model-id NeoQuasar/Kronos-base \
    --tokenizer-id NeoQuasar/Kronos-Tokenizer-base \
    --resume
fi

if [[ "$RUN_PREDICTOR_FINETUNE" == "1" || "$RUN_TOKENIZER_FINETUNE" == "1" ]]; then
  echo "== Prepare Kronos fine-tune data =="
  python scripts/prepare_kronos_sp500.py \
    --out-dir data/kronos/sp500_daily \
    --lookback-window 512 \
    --predict-window 20 \
    --train-start 2000-01-03 \
    --train-end 2018-12-31 \
    --val-start 2019-01-01 \
    --val-end 2020-12-31 \
    --test-start 2021-01-01 \
    --test-end 2026-06-16

  CONFIG_PATH="$KRONOS_ROOT/finetune/config.py"
  cp "$CONFIG_PATH" "$CONFIG_PATH.cloud_backup"
  cat > "$CONFIG_PATH" <<PY
class Config:
    def __init__(self):
        self.qlib_data_path = ""
        self.instrument = "sp500"
        self.dataset_begin_time = "2000-01-03"
        self.dataset_end_time = "2026-06-16"
        self.lookback_window = 512
        self.predict_window = 20
        self.max_context = 512
        self.feature_list = ["open", "high", "low", "close", "vol", "amt"]
        self.time_feature_list = ["minute", "hour", "weekday", "day", "month"]
        self.train_time_range = ["2000-01-03", "2018-12-31"]
        self.val_time_range = ["2019-01-01", "2020-12-31"]
        self.test_time_range = ["2021-01-01", "2026-06-16"]
        self.backtest_time_range = ["2021-01-01", "2026-06-16"]
        self.dataset_path = "$PROJECT_ROOT/data/kronos/sp500_daily"
        self.clip = 5.0
        self.epochs = $FINETUNE_EPOCHS
        self.log_interval = 50
        self.batch_size = $FINETUNE_BATCH_SIZE
        self.n_train_iter = 2000 * self.batch_size
        self.n_val_iter = 400 * self.batch_size
        self.tokenizer_learning_rate = 2e-4
        self.predictor_learning_rate = 1e-5
        self.accumulation_steps = 1
        self.adam_beta1 = 0.9
        self.adam_beta2 = 0.95
        self.adam_weight_decay = 0.1
        self.seed = 100
        self.use_comet = False
        self.comet_config = {"api_key": "", "project_name": "", "workspace": ""}
        self.comet_tag = "sp500_kronos"
        self.comet_name = "sp500_kronos"
        self.save_path = "$PROJECT_ROOT/output/kronos_finetune"
        self.tokenizer_save_folder_name = "tokenizer_sp500"
        self.predictor_save_folder_name = "predictor_sp500"
        self.backtest_save_folder_name = "backtest_sp500"
        self.backtest_result_path = "$PROJECT_ROOT/output/kronos_finetune/backtest"
        self.pretrained_tokenizer_path = "NeoQuasar/Kronos-Tokenizer-base"
        self.pretrained_predictor_path = "NeoQuasar/Kronos-small"
        self.finetuned_tokenizer_path = (
            f"{self.save_path}/{self.tokenizer_save_folder_name}/checkpoints/best_model"
        )
        if "$RUN_TOKENIZER_FINETUNE" != "1":
            self.finetuned_tokenizer_path = self.pretrained_tokenizer_path
        self.finetuned_predictor_path = (
            f"{self.save_path}/{self.predictor_save_folder_name}/checkpoints/best_model"
        )
        self.backtest_n_symbol_hold = 50
        self.backtest_n_symbol_drop = 5
        self.backtest_hold_thresh = 5
        self.inference_T = 0.6
        self.inference_top_p = 0.9
        self.inference_top_k = 0
        self.inference_sample_count = 5
        self.backtest_batch_size = 1000
        self.backtest_benchmark = "SP500"
PY

  if [[ "$RUN_TOKENIZER_FINETUNE" == "1" ]]; then
    echo "== Fine-tune tokenizer =="
    (cd "$KRONOS_ROOT" && torchrun --standalone --nproc_per_node=1 finetune/train_tokenizer.py)
  fi

  if [[ "$RUN_PREDICTOR_FINETUNE" == "1" ]]; then
    echo "== Fine-tune predictor =="
    (cd "$KRONOS_ROOT" && torchrun --standalone --nproc_per_node=1 finetune/train_predictor.py)
  fi
fi

echo "Cloud Kronos plan complete."
