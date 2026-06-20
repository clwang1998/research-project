# round13 Copilot GPT-5.5 Fallback Review

Reviewer: GitHub Copilot GPT-5.5 fallback
Prompt file: tmp/copilot_opus_review_prompt.md
Generated: 2026-06-20T13:30:19+00:00

---

## Findings

| Severity | Location | Impact | Concrete fix |
|---|---|---|---|
| **Medium** | `scripts/run_model_pipeline.py`, `infer_horizon_days()` | The regex only accepts columns ending exactly in `_fwd_{N}d`. If the repo later uses valid target variants with suffixes after the horizon, the pipeline will fail early. Current documented targets appear compatible, so this is not blocking. | Keep if target naming is intentionally strict, or document the naming contract; otherwise relax parsing to find `_fwd_{N}d` before optional suffixes. |
| **Low** | `scripts/run_model_pipeline.py`, `embargo_split_start()` | `embargo_days` removes the first N dates of each split after purge, so a 5D horizon leaves validation starting after 5 in-split dates. This is defensible, but the implementation is “start-of-block embargo,” not a symmetric purge/embargo around every train/test boundary or a full walk-forward embargo. | Ensure docs consistently describe this as anchored-split start embargo. Do not imply full López de Prado walk-forward CV is implemented. |
| **Low** | `scripts/run_model_pipeline.py`, graph embedding path | `--include-graph-embeddings` will hard-fail if the default graph embedding parquet is absent. That is fine for explicit opt-in, but reproducibility docs should mention the required graph generation step before using the flag. | Add a short prerequisite near graph-embedding commands/docs. |
| **Low** | `docs/data_leakage_review.md` | The report says several fixes are “已修复” while also warning that real-data reruns and broader script review are still required. This can still over-certify the leakage state for downstream readers. | Rename headings to “已在主脚本实现/待真实数据复核” or explicitly separate implementation status from empirical validation status. |

No P0/P1 blocking issue is visible in the supplied diff/content. The core purge, execution-lag, and split-audit logic appears directionally correct for the anchored split. **Residual risk:** I could not execute the code or inspect omitted file sections, so model/preprocessor interactions, real-data split audits, and any downstream aggregation scripts remain unverified.

