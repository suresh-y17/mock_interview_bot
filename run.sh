#!/usr/bin/env bash
# One-command start: seeds the DB if missing/empty, then serves the app.
set -euo pipefail
cd "$(dirname "$0")"

needs_seed=0
if [ ! -f mockinterview.db ]; then
  needs_seed=1
elif [ ! -s mockinterview.db ]; then
  # A 0-byte file is worse than no file: the server starts, then 500s everywhere.
  echo "Found an empty mockinterview.db — reseeding."
  needs_seed=1
fi

if [ "$needs_seed" = "1" ]; then
  rm -f mockinterview.db
  python3 -m app.db
fi

exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
