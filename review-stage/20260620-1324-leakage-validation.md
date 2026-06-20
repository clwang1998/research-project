# Leakage-Control Validation Artifact

Generated for the ARIS cloud technical-report review loop.

## Commands

```bash
python3 -m py_compile scripts/run_model_pipeline.py scripts/run_target_model_experiments.py
```

```bash
python3 - <<'PY'
import importlib.util
from pathlib import Path
import sys
import pandas as pd

spec = importlib.util.spec_from_file_location("run_model_pipeline", Path("scripts/run_model_pipeline.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

assert mod.infer_horizon_days("target_ret_fwd_5d", "target_excess_sector_fwd_5d") == 5
try:
    mod.infer_horizon_days("target_ret_fwd_5d", "target_ret_fwd_20d")
except ValueError:
    pass
else:
    raise AssertionError("horizon mismatch did not raise")

rows = []
for symbol in ["AAA", "BBB", "CCC"]:
    for i, date in enumerate(pd.bdate_range("2020-12-01", "2021-01-29")):
        rows.append({
            "date": date,
            "symbol": symbol,
            "sector": "Tech",
            "sub_industry": "Software",
            "hq_state": "CA",
            "hq_region": "West",
            "target_ret_fwd_5d": float(i),
            "target_excess_sector_fwd_5d": float(i) / 10.0,
        })
panel = pd.DataFrame(rows)
lagged = mod.attach_effective_labels(panel, "target_excess_sector_fwd_5d", "target_ret_fwd_5d", 5, 1)
raw = mod.split_masks(lagged, train_end="2020-12-31", val_end="2021-01-15")
purged = mod.apply_purge_embargo(lagged, raw, train_end="2020-12-31", val_end="2021-01-15", embargo_days=2)
audit = mod.split_audit(lagged, raw, purged)
assert audit["train"]["label_end_max"] == "2020-12-31", audit
assert audit["val"]["label_end_max"] == "2021-01-15", audit
assert audit["train"]["dropped_rows"] == 18, audit
assert audit["val"]["dropped_rows"] == 24, audit
assert audit["test"]["dropped_rows"] == 6, audit
print("synthetic leakage-control checks passed")
print(audit)
PY
```

## Result

```text
synthetic leakage-control checks passed
{'train': {'raw_rows': 69, 'kept_rows': 51, 'dropped_rows': 18, 'dates': 17, 'date_min': '2020-12-01', 'date_max': '2020-12-23', 'label_end_max': '2020-12-31'}, 'val': {'raw_rows': 33, 'kept_rows': 9, 'dropped_rows': 24, 'dates': 3, 'date_min': '2021-01-05', 'date_max': '2021-01-07', 'label_end_max': '2021-01-15'}, 'test': {'raw_rows': 12, 'kept_rows': 6, 'dropped_rows': 6, 'dates': 2, 'date_min': '2021-01-20', 'date_max': '2021-01-21', 'label_end_max': '2021-01-29'}}
```

## Cloud Rerun

After installing the project dependencies in the cloud project-local `.venv`, the
same validation passed on `/root/research_project_cloud` with
`.venv/bin/python`.

```text
cloud synthetic leakage-control checks passed
{'train': {'raw_rows': 69, 'kept_rows': 51, 'dropped_rows': 18, 'dates': 17, 'date_min': '2020-12-01', 'date_max': '2020-12-23', 'label_end_max': '2020-12-31'}, 'val': {'raw_rows': 33, 'kept_rows': 9, 'dropped_rows': 24, 'dates': 3, 'date_min': '2021-01-05', 'date_max': '2021-01-07', 'label_end_max': '2021-01-15'}, 'test': {'raw_rows': 12, 'kept_rows': 6, 'dropped_rows': 6, 'dates': 2, 'date_min': '2021-01-20', 'date_max': '2021-01-21', 'label_end_max': '2021-01-29'}}
```
