#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <archive-path> <user@host:/remote/path/>"
  echo "Example: $0 dist/research_project_cloud_minimal.tar.gz ubuntu@1.2.3.4:/home/ubuntu/"
  exit 2
fi

ARCHIVE_PATH="$1"
REMOTE_DEST="$2"

if [[ ! -f "$ARCHIVE_PATH" ]]; then
  echo "Archive not found: $ARCHIVE_PATH" >&2
  exit 1
fi

scp "$ARCHIVE_PATH" "$REMOTE_DEST"
