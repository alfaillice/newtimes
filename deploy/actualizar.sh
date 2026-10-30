#!/usr/bin/env bash
# Lo ejecuta el temporizador cada 5 minutos (usuario newtimes).
# Descarga cambios de GitHub y reconstruye la web si hay novedades,
# y en cualquier caso al menos una vez por hora.
set -euo pipefail
REPO="/srv/newtimes/repo"
WEB="/srv/newtimes/public"
MARCA="/srv/newtimes/.ultima-construccion"

cd "$REPO"
git fetch -q origin main
ANTES=$(git rev-parse HEAD)
DESPUES=$(git rev-parse origin/main)
CAMBIOS=0
if [ "$ANTES" != "$DESPUES" ]; then
  git reset -q --hard origin/main
  CAMBIOS=1
  echo "nuevo commit: $(git log -1 --format='%h %s')"
fi

VIEJA=1
if [ -f "$MARCA" ] && [ -n "$(find "$MARCA" -mmin -60)" ]; then VIEJA=0; fi

if [ "$CAMBIOS" = 1 ] || [ "$VIEJA" = 1 ] || [ ! -d "$WEB" ]; then
  python3 "$REPO/build.py" --out "$WEB"
  touch "$MARCA"
fi
