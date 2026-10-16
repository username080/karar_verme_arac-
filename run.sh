#!/usr/bin/env bash
# MakeUrChoice başlatıcı: konteyneri kurar, başlatır ve tarayıcıda açar.
# Kullanım: ./run.sh [stop|logs|rebuild]
set -euo pipefail

NAME="makeurchoice"
VOLUME="makeurchoice-data"
PORT=8767
URL="http://localhost:${PORT}"
cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"

if command -v docker >/dev/null 2>&1; then
  CTR=docker
elif command -v podman >/dev/null 2>&1; then
  CTR=podman
else
  echo "Hata: ne 'docker' ne de 'podman' bulundu. Birini kurup tekrar deneyin." >&2
  exit 1
fi

exists() { "$CTR" container inspect "$NAME" >/dev/null 2>&1; }
remove() { exists && "$CTR" rm -f "$NAME" >/dev/null || true; }

wait_ready() {
  local i
  for i in $(seq 1 60); do
    if command -v curl >/dev/null 2>&1; then
      curl -fs "${URL}/healthz" >/dev/null 2>&1 && return 0
    elif (exec 3<>"/dev/tcp/127.0.0.1/${PORT}") 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}

open_browser() {
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$URL" >/dev/null 2>&1 || true
  fi
}

start() {
  local rebuild="${1:-}"
  # Her başlatmada derle: katman önbelleği sayesinde değişmediyse anında biter,
  # kod güncellendiyse eski imaj yerine yenisi kullanılır.
  echo "İmaj derleniyor..."
  if [ "$rebuild" = rebuild ]; then
    "$CTR" build --no-cache -t "$NAME" .
  else
    "$CTR" build -t "$NAME" .
  fi
  # Konteyner eski imajdan çalışıyor olabilir; veri volume'da olduğu için yeniden oluşturmak güvenli.
  remove
  if ! exists; then
    "$CTR" run -d --name "$NAME" -p "${PORT}:${PORT}" \
      -v "${VOLUME}:/data" --restart unless-stopped "$NAME" >/dev/null
  fi
  echo "Hazır olması bekleniyor..."
  if ! wait_ready; then
    echo "Hata: uygulama başlamadı. Kayıtlar:" >&2
    "$CTR" logs --tail 30 "$NAME" >&2 || true
    exit 1
  fi
  echo "MakeUrChoice çalışıyor: $URL"
  open_browser
}

case "${1:-start}" in
  start)   start ;;
  rebuild) start rebuild ;;
  stop)    exists && "$CTR" stop "$NAME" >/dev/null && echo "Durduruldu (veri korunur)." || echo "Çalışan konteyner yok." ;;
  logs)    exists || { echo "Konteyner yok." >&2; exit 1; }; "$CTR" logs -f "$NAME" ;;
  *)       echo "Kullanım: $0 [stop|logs|rebuild]" >&2; exit 2 ;;
esac
