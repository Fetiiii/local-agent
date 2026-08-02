#!/usr/bin/env bash
# Start the Local Agent web server.
set -e
cd "$(dirname "$0")"

[ -d .venv ] || { echo "❌ .venv yok — önce ./setup.sh çalıştır."; exit 1; }
[ -f .env ]  || { echo "❌ .env yok — önce ./setup.sh çalıştır."; exit 1; }

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

# Best-effort model-backend reachability hint (non-fatal).
BASE_URL=$(grep -E '^OPENAI_BASE_URL=' .env | cut -d= -f2- | tr -d '"')
PROVIDER=$(grep -E '^LLM_PROVIDER=' .env | cut -d= -f2- | tr -d '"')
if [ "$PROVIDER" = "openai" ] && [ -n "$BASE_URL" ]; then
  curl -s --max-time 2 "${BASE_URL%/}/models" >/dev/null 2>&1 \
    || echo "⚠️ Model backend ($BASE_URL) yanıt vermiyor — llama-server açık mı?"
fi

echo "🚀 http://${HOST}:${PORT}"
exec .venv/bin/uvicorn server:app --host "$HOST" --port "$PORT"
