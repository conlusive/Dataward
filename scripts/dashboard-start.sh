#!/bin/sh
# Start the dashboard container. The image carries the export as of its build; only when there is
# none (a local build, or the download at build time failed) is it fetched first, if
# DASHBOARD_DATA_URL is set. Then serve on the port the host gives us ($PORT on Render), 8501 otherwise.
set -eu

if [ ! -f "${DASHBOARD_DATA_DIR:-data/export}/last_update.json" ]; then
  python -m jobmarket.dashboard_sync || echo "data sync failed; starting with the data that is there"
fi

# no file watcher: nothing edits the code of a container, and watching costs CPU on a small plan
exec streamlit run dashboard/app.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT:-8501}" \
  --server.headless=true \
  --server.fileWatcherType=none \
  --browser.gatherUsageStats=false
