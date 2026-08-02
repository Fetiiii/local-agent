#!/usr/bin/env bash
# One-time setup: Python venv + deps + sandbox image + .env.
set -e
cd "$(dirname "$0")"

echo "🔧 Local Agent kurulumu"

# ── Python venv + dependencies ────────────────────────────────────
if command -v uv >/dev/null 2>&1; then
  echo "→ uv ile Python 3.12 venv + bağımlılıklar"
  uv venv --python 3.12 .venv
  uv pip install -r requirements.txt --python .venv/bin/python
else
  echo "→ python venv + pip (uv bulunamadı)"
  python3 -m venv .venv
  .venv/bin/pip install -U pip
  .venv/bin/pip install -r requirements.txt
fi

# ── .env ──────────────────────────────────────────────────────────
if [ ! -f .env ]; then
  cp .env.example .env
  echo "→ .env oluşturuldu — düzenle: MODEL_NAME, LLM_PROVIDER (ollama/openai), OPENAI_BASE_URL"
else
  echo "→ .env zaten var, dokunulmadı"
fi

# ── Sandbox Docker image ──────────────────────────────────────────
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo "→ Sandbox Docker imajı derleniyor (ilk sefer birkaç dk)"
  docker build -t localagent-sandbox:latest -f docker/sandbox.Dockerfile .
else
  echo "⚠️ Docker yok/çalışmıyor — kod sandbox'ı devre dışı."
  echo "   .env'de SANDBOX_BACKEND=local yaparsan host'ta (izolasyonsuz) çalışır."
fi

echo ""
echo "✅ Kurulum tamam."
echo "   1) Model backend'ini başlat (Ollama, ya da llama.cpp llama-server)."
echo "   2) ./run.sh  →  http://localhost:8000"
