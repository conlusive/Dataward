#!/bin/sh
# Start the dashboard container. The image carries the export as of its build. If there is none, or
# it is stale (a host that slept for days, an old image), it is fetched before the server starts, if
# DASHBOARD_DATA_URL is set: the first visitor must not see yesterday's data for a minute. Fresh data
# starts at once. Then serve on the port the host gives us ($PORT on Render), 8501 otherwise.
set -eu

python -m jobmarket.dashboard_sync || echo "data sync failed; starting with the data that is there"

# no file watcher: nothing edits the code of a container, and watching costs CPU on a small plan
exec streamlit run dashboard/app.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT:-8501}" \
  --server.headless=true \
  --server.fileWatcherType=none \
  --browser.gatherUsageStats=false
