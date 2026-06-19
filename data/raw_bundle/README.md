# Raw Data Bundle

This directory stores the raw S&P 500 CSV data as split archive chunks so the
data can live in GitHub without exceeding the per-file upload limit.

To rebuild locally:

```bash
scripts/package_raw_data_bundle.sh
```

To unpack manually:

```bash
cat research_project_raw_data.tar.gz.part-* > /tmp/research_project_raw_data.tar.gz
tar -xzf /tmp/research_project_raw_data.tar.gz
```
