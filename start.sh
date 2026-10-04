#!/bin/sh
set -eu

cd /app/backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &

cd /app/frontend
export BACKEND_URL="http://127.0.0.1:8000"

exec python -m streamlit run app.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT:-8501}" \
  --server.headless=true \
  --server.enableCORS=true \
  --server.enableXsrfProtection=true
