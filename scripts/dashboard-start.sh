#!/bin/sh
# Start the dashboard container: fetch the public export first (when DASHBOARD_DATA_URL is set), then
# serve on the port the host gives us ($PORT on Render and similar), 8501 otherwise.
set -eu

python -m jobmarket.dashboard_sync || echo "data sync failed; starting with the data that is there"

exec streamlit run dashboard/app.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT:-8501}" \
  --server.headless=true \
  --browser.gatherUsageStats=false
