#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

WAIT_PID="${WAIT_PID:?Set WAIT_PID to the zero-shot process pid}"
WAIT_LOG="${WAIT_LOG:?Set WAIT_LOG to the zero-shot log path}"
POLL_SECONDS="${POLL_SECONDS:-300}"
FINETUNE_EPOCHS="${FINETUNE_EPOCHS:-3}"
FINETUNE_BATCH_SIZE="${FINETUNE_BATCH_SIZE:-64}"

echo "Waiting for zero-shot PID $WAIT_PID"
echo "Zero-shot log: $WAIT_LOG"

while kill -0 "$WAIT_PID" 2>/dev/null; do
  sleep "$POLL_SECONDS"
done

if ! grep -q "Cloud Kronos plan complete." "$WAIT_LOG"; then
  echo "Zero-shot plan did not complete cleanly; predictor fine-tune will not start."
  echo "Last zero-shot log lines:"
  tail -n 120 "$WAIT_LOG" || true
  exit 1
fi

echo "Zero-shot plan complete. Starting predictor-only fine-tune."

RUN_SMOKE_SAMPLE=0 \
RUN_SMALL_FULL=0 \
RUN_BASE_FULL=0 \
RUN_PREDICTOR_FINETUNE=1 \
RUN_TOKENIZER_FINETUNE=0 \
FINETUNE_EPOCHS="$FINETUNE_EPOCHS" \
FINETUNE_BATCH_SIZE="$FINETUNE_BATCH_SIZE" \
bash scripts/run_cloud_kronos_plan.sh
