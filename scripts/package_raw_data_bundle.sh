#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Package local raw CSV data into GitHub-safe split bundle files.

Usage:
  scripts/package_raw_data_bundle.sh

Environment overrides:
  STOCKS_CSV=data/raw/sp500_stocks.csv
  COMPANIES_CSV=data/raw/sp500_companies.csv
  RAW_BUNDLE_DIR=data/raw_bundle
  RAW_BUNDLE_NAME=research_project_raw_data.tar.gz
  SPLIT_SIZE=50m
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

STOCKS_CSV="${STOCKS_CSV:-data/raw/sp500_stocks.csv}"
COMPANIES_CSV="${COMPANIES_CSV:-data/raw/sp500_companies.csv}"
RAW_BUNDLE_DIR="${RAW_BUNDLE_DIR:-data/raw_bundle}"
RAW_BUNDLE_NAME="${RAW_BUNDLE_NAME:-research_project_raw_data.tar.gz}"
SPLIT_SIZE="${SPLIT_SIZE:-50m}"
WORK_DIR="${WORK_DIR:-dist/raw_bundle_work}"
ARCHIVE_PATH="$WORK_DIR/$RAW_BUNDLE_NAME"

for path in "$STOCKS_CSV" "$COMPANIES_CSV"; do
  if [[ ! -f "$path" ]]; then
    echo "Missing raw data file: $path" >&2
    exit 2
  fi
done

mkdir -p "$WORK_DIR" "$RAW_BUNDLE_DIR"
rm -f "$ARCHIVE_PATH" "$RAW_BUNDLE_DIR/$RAW_BUNDLE_NAME".part-* "$RAW_BUNDLE_DIR/$RAW_BUNDLE_NAME.sha256"

tar -czf "$ARCHIVE_PATH" "$STOCKS_CSV" "$COMPANIES_CSV"
split -b "$SPLIT_SIZE" "$ARCHIVE_PATH" "$RAW_BUNDLE_DIR/$RAW_BUNDLE_NAME.part-"
shasum -a 256 "$ARCHIVE_PATH" | sed "s#  $ARCHIVE_PATH#  $RAW_BUNDLE_NAME#" > "$RAW_BUNDLE_DIR/$RAW_BUNDLE_NAME.sha256"

cat > "$RAW_BUNDLE_DIR/README.md" <<EOF
# Raw Data Bundle

This directory stores the raw S&P 500 CSV data as split archive chunks so the
data can live in GitHub without exceeding the per-file upload limit.

To rebuild locally:

\`\`\`bash
scripts/package_raw_data_bundle.sh
\`\`\`

To unpack manually:

\`\`\`bash
cat $RAW_BUNDLE_NAME.part-* > /tmp/$RAW_BUNDLE_NAME
tar -xzf /tmp/$RAW_BUNDLE_NAME
\`\`\`
EOF

echo "Created split raw bundle under $RAW_BUNDLE_DIR"
ls -lh "$RAW_BUNDLE_DIR"
