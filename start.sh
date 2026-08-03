#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Local Agent — TEK TIKLA tüm sistem:
#   1) frontend'i derler (gerekirse)
#   2) model backend'ini (llama.cpp llama-server) başlatır
#   3) web sunucusunu (FastAPI/uvicorn) başlatır
#   4) tarayıcıyı açar
# Ctrl+C → hepsini birden temiz kapatır.
#
# Ayarlar .env'den okunur. İstersen .env'e şunları ekleyebilirsin:
#   LLAMA_SERVER_BIN=/yol/llama-server        # binary yolu (yoksa otomatik bulunur)
#   LLAMA_SERVER_ARGS=-ngl 99 --flash-attn on # GPU offload vb. ekstra bayraklar
# ─────────────────────────────────────────────────────────────────────────────
set -uo pipefail
cd "$(dirname "$0")"

[ -d .venv ] || { echo "❌ .venv yok — önce ./setup.sh çalıştır."; exit 1; }
[ -f .env ]  || { echo "❌ .env yok — önce ./setup.sh çalıştır."; exit 1; }
mkdir -p logs

# ── .env'den değer oku ───────────────────────────────────────────────────────
env_get() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'; }
PROVIDER=$(env_get LLM_PROVIDER)
BASE_URL=$(env_get OPENAI_BASE_URL)
MODEL=$(env_get MODEL_NAME)
NUM_CTX=$(env_get NUM_CTX); NUM_CTX=${NUM_CTX:-8192}
LLAMA_SERVER_BIN=$(env_get LLAMA_SERVER_BIN)
LLAMA_SERVER_ARGS=$(env_get LLAMA_SERVER_ARGS)

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

# model backend host/port'u BASE_URL'den türet
MODEL_HOST=$(echo "$BASE_URL" | sed -E 's#.*://([^:/]+).*#\1#'); MODEL_HOST=${MODEL_HOST:-127.0.0.1}
MODEL_PORT=$(echo "$BASE_URL" | sed -E 's#.*://[^:/]+:([0-9]+).*#\1#'); MODEL_PORT=${MODEL_PORT:-8080}

PIDS=()
cleanup() {
  echo ""
  echo "🛑 Kapatılıyor…"
  for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill "$p" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

model_up() { curl -s --max-time 2 "http://${MODEL_HOST}:${MODEL_PORT}/health" >/dev/null 2>&1; }
web_up()   { curl -s --max-time 1 "http://${HOST}:${PORT}/" >/dev/null 2>&1; }

# ── 1) Frontend build (yoksa) ────────────────────────────────────────────────
if [ ! -f webui/dist/index.html ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "🎨 Frontend derleniyor (ilk sefer birkaç dk sürebilir)…"
    ( cd webui && { [ -d node_modules ] || npm install; } && npm run build ) \
      || echo "⚠️ Frontend derlenemedi — eski vanilla UI kullanılacak."
  else
    echo "⚠️ npm bulunamadı — eski vanilla UI kullanılacak (frontend build atlandı)."
  fi
fi

# ── 2) Model backend (llama.cpp) ─────────────────────────────────────────────
if [ "$PROVIDER" = "openai" ]; then
  if model_up; then
    echo "✅ Model backend zaten açık (:$MODEL_PORT)"
  else
    BIN="${LLAMA_SERVER_BIN:-}"
    [ -z "$BIN" ] && BIN="$(command -v llama-server 2>/dev/null || true)"
    [ -z "$BIN" ] && [ -x "$HOME/llama.cpp/build/bin/llama-server" ] && BIN="$HOME/llama.cpp/build/bin/llama-server"

    if [ -n "$BIN" ] && [ -x "$BIN" ] && [ -f "$MODEL" ]; then
      # -ngl geçmiyoruz → llama.cpp otomatik VRAM'e sığdırır (autofit).
      # GPU offload'ı elle kontrol etmek istersen .env'de LLAMA_SERVER_ARGS ayarla.
      EXTRA="${LLAMA_SERVER_ARGS:-}"
      echo "🧠 Model backend başlatılıyor: $(basename "$MODEL")  (:$MODEL_PORT, ctx=$NUM_CTX, args: ${EXTRA:-autofit})"
      # shellcheck disable=SC2086
      "$BIN" -m "$MODEL" --host "$MODEL_HOST" --port "$MODEL_PORT" -c "$NUM_CTX" $EXTRA \
        > logs/llama-server.log 2>&1 &
      PIDS+=("$!")
      printf "   hazırlanıyor"
      for _ in $(seq 1 90); do model_up && break; printf "."; sleep 2; done
      if model_up; then echo " ✓"; else
        echo " ⚠️ Model :$MODEL_PORT hazır değil — logs/llama-server.log bak. UI yine de açılıyor."
      fi
    else
      echo "⚠️ llama-server ya da model bulunamadı — modeli elle başlat."
      echo "   binary: ${BIN:-<yok>}   model: ${MODEL:-<yok>}"
      echo "   (İpucu: .env'e LLAMA_SERVER_BIN / LLAMA_SERVER_ARGS ekleyebilirsin.)"
    fi
  fi
elif [ "$PROVIDER" = "ollama" ]; then
  echo "ℹ️ Provider=ollama — 'ollama serve' çalışıyor varsayılıyor."
fi

# ── 3) Web sunucusu ──────────────────────────────────────────────────────────
if web_up; then
  echo "⚠️ :$PORT zaten kullanımda — mevcut sunucuya bağlanılıyor."
else
  echo "🚀 Web sunucusu: http://${HOST}:${PORT}"
fi

# ── 4) Tarayıcıyı hazır olunca aç (arka planda) ──────────────────────────────
(
  for _ in $(seq 1 40); do web_up && break; sleep 1; done
  ( xdg-open "http://${HOST}:${PORT}" >/dev/null 2>&1 \
    || sensible-browser "http://${HOST}:${PORT}" >/dev/null 2>&1 \
    || true )
) &
PIDS+=("$!")

echo "✅ Sistem açılıyor — kapatmak için bu pencerede Ctrl+C."
echo "   (uvicorn logları aşağıda; model logları logs/llama-server.log)"
echo ""

# uvicorn ÖN PLANDA → logları burada akar; Ctrl+C trap ile her şeyi kapatır.
.venv/bin/uvicorn server:app --host "$HOST" --port "$PORT"
