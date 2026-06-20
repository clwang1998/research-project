# round10 Copilot GPT-5.5 Fallback Review

Reviewer: GitHub Copilot GPT-5.5 fallback
Prompt file: tmp/copilot_opus_review_prompt.md
Generated: 2026-06-20T13:05:37+00:00

---

| Severity | Location | Finding / impact | Concrete fix |
|---|---|---|---|
| **High** | `docs/data_leakage_review.md`, “修改文件清单” | The doc claims leakage fixes landed in `scripts/autoresearchclaw_param_search.py` and `scripts/build_horizon_comparison.py`, but those files are not in the supplied status/diff/scope. This can falsely certify that refinement runs inherit lag/embargo and that horizon winners no longer use test-set selection. | Either include/review those code changes, or revise the doc to mark them pending/unverified. Do not use this leakage review as final evidence until resolved. |
| **Medium** | `scripts/run_model_pipeline.py`, after purge/embargo in `main()` | No fail-fast validation ensures purged/embargoed train/val/test splits still have enough rows/dates. Long horizons, smoke windows, or high `--embargo-days` can produce empty/degenerate splits and later fail opaquely or emit misleading NaNs. | After `split_audit`, raise a clear `ValueError` if required splits have zero rows, too few dates, or insufficient names per date. Add a synthetic split test for 5D and 120/150D. |
| **Medium** | `scripts/run_target_model_experiments.py` command construction; `run_model_pipeline.py` run naming | Execution lag and embargo settings are forwarded/configured but do not appear to be encoded in generated run names. Runs with lag `0` vs `1`, or default embargo vs `--embargo-days 0`, can overwrite or be confused with each other. | Add lag/embargo suffixes to auto-generated run names, or require explicit run names when non-default split controls are used. |
| **Low** | `docs/feature_catalog.md`; `scripts/make_features.py` | Docs state `targets.parquet` now has 48 columns, but this is only true after regenerating processed features. Existing stale processed artifacts will make 120D/150D target commands fail. | Add an explicit “requires rerun of `make_features.py` / full data pipeline” note and make missing target-column errors actionable. |
| **Low** | `scripts/run_model_pipeline.py` leakage helpers | No test evidence is supplied for `infer_horizon_days`, `attach_effective_labels`, `apply_purge_embargo`, or experiment-runner arg propagation. These are central leakage controls. | Add small synthetic-panel regression tests checking shifted labels, `_label_end_date`, split purge, embargo removal, and horizon mismatch errors. |

No P0 unsafe-shell or credential-risk issue is visible in the supplied diff. The main blocking concern is the documentation/code-scope mismatch around claimed leakage fixes outside the reviewed changes; resolve that before treating the review/report as final.

