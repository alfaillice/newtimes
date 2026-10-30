#!/usr/bin/env bash
# Instalador de NewTimes.news para Ubuntu 22.04/24.04.
# Uso (como usuario con sudo):  sudo bash instalar.sh
# Se puede ejecutar varias veces sin romper nada.
set -euo pipefail

DOMINIO="newtimes.news"
REPO_SSH="git@github.com:alfaillice/newtimes.git"
REPO_HTTPS="https://github.com/alfaillice/newtimes.git"
USUARIO="newtimes"
BASE="/srv/newtimes"
REPO="$BASE/repo"
WEB="$BASE/public"
ACME="/var/www/letsencrypt"

paso() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '    \033[32m✔\033[0m %s\n' "$*"; }
falla(){ printf '\n\033[1;31mERROR: %s\033[0m\n' "$*"; exit 1; }

[ "$(id -u)" -eq 0 ] || falla "Ejecútalo con sudo: sudo bash $0"

paso "1/8 Instalando paquetes"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx git python3 python3-jinja2 python3-markdown python3-yaml python3-pil certbot >/dev/null
ok "nginx, git, Python y certbot instalados"

paso "2/8 Comprobando que nada más ocupa los puertos 80 y 443"
OTROS=$(ss -ltnpH '( sport = :80 or sport = :443 )' 2>/dev/null | grep -v nginx || true)
if [ -n "$OTROS" ]; then
  echo "$OTROS"
  falla "Otro programa usa el puerto 80/443 (arriba). Páralo (por ejemplo: sudo systemctl disable --now apache2) y vuelve a ejecutar el instalador."
fi
ok "Puertos libres o en manos de nginx"

paso "3/8 Usuario y carpetas"
id "$USUARIO" >/dev/null 2>&1 || useradd --system --create-home --home-dir "/home/$USUARIO" --shell /bin/bash "$USUARIO"
mkdir -p "$BASE" "$ACME"
chown "$USUARIO:$USUARIO" "$BASE"
chmod 755 "$BASE"
ok "Usuario '$USUARIO' y carpeta $BASE"

paso "4/8 Acceso de lectura al repositorio de GitHub"
if GIT_TERMINAL_PROMPT=0 sudo -u "$USUARIO" git ls-remote "$REPO_HTTPS" >/dev/null 2>&1; then
  ORIGEN="$REPO_HTTPS"
  ok "Repositorio público: se descarga sin clave"
else
  ORIGEN="$REPO_SSH"
  CLAVE="/home/$USUARIO/.ssh/id_ed25519"
  if [ ! -f "$CLAVE" ]; then
    sudo -u "$USUARIO" mkdir -p "/home/$USUARIO/.ssh"
    sudo -u "$USUARIO" ssh-keygen -q -t ed25519 -N "" -C "newtimes-vps-solo-lectura" -f "$CLAVE"
  fi
  sudo -u "$USUARIO" sh -c "ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null; sort -u -o ~/.ssh/known_hosts ~/.ssh/known_hosts"
  if ! sudo -u "$USUARIO" git ls-remote "$REPO_SSH" >/dev/null 2>&1; then
    echo
    echo "    Repositorio privado: añade esta clave en GitHub para que el servidor pueda leerlo."
    echo "    https://github.com/alfaillice/newtimes/settings/keys/new"
    echo "    Title: VPS. Key: la línea de abajo. NO marques 'Allow write access'."
    echo
    cat "$CLAVE.pub"
    echo
    read -r -p "    Pulsa Enter cuando la hayas añadido... " _ </dev/tty
    sudo -u "$USUARIO" git ls-remote "$REPO_SSH" >/dev/null 2>&1 || falla "GitHub sigue sin aceptar la clave. Revisa que la pegaste entera y vuelve a ejecutar el instalador."
  fi
  ok "El servidor puede leer el repositorio con su clave de solo lectura"
fi

paso "5/8 Descargando y construyendo la web"
if [ ! -d "$REPO/.git" ]; then
  sudo -u "$USUARIO" git clone -q "$ORIGEN" "$REPO"
else
  sudo -u "$USUARIO" git -C "$REPO" remote set-url origin "$ORIGEN"
  sudo -u "$USUARIO" git -C "$REPO" fetch -q origin main
  sudo -u "$USUARIO" git -C "$REPO" reset -q --hard origin/main
fi
sudo -u "$USUARIO" python3 "$REPO/build.py" --out "$WEB"
ok "Web construida en $WEB"

paso "6/8 Configurando nginx"
install -m 644 "$REPO/deploy/nginx-cabeceras.conf" /etc/nginx/snippets/newtimes-cabeceras.conf
# Se desactivan otras webs sin borrarlas (siguen en /etc/nginx/sites-available)
for s in /etc/nginx/sites-enabled/*; do
  [ -e "$s" ] || continue
  [ "$(basename "$s")" = "newtimes" ] && continue
  echo "    desactivando $(basename "$s") (se conserva en sites-available)"
  rm -f "$s"
done
CERT="/etc/letsencrypt/live/$DOMINIO/fullchain.pem"
if [ -f "$CERT" ]; then
  sed -e "s|__DOMINIO__|$DOMINIO|g" -e "s|__WEB__|$WEB|g" -e "s|__ACME__|$ACME|g" "$REPO/deploy/nginx-https.conf" > /etc/nginx/sites-available/newtimes
else
  sed -e "s|__DOMINIO__|$DOMINIO|g" -e "s|__WEB__|$WEB|g" -e "s|__ACME__|$ACME|g" "$REPO/deploy/nginx-http.conf" > /etc/nginx/sites-available/newtimes
fi
ln -sf /etc/nginx/sites-available/newtimes /etc/nginx/sites-enabled/newtimes
nginx -t -q && systemctl enable -q nginx && systemctl reload nginx || systemctl restart nginx
ok "nginx sirve la web"

paso "7/8 Certificado HTTPS"
if [ ! -f "$CERT" ]; then
  DOMS=(-d "$DOMINIO")
  if getent hosts "www.$DOMINIO" >/dev/null; then DOMS+=(-d "www.$DOMINIO"); fi
  certbot certonly --webroot -w "$ACME" "${DOMS[@]}" --non-interactive --agree-tos \
    --register-unsafely-without-email --deploy-hook "systemctl reload nginx" \
    || falla "No se pudo obtener el certificado. Comprueba en Cloudflare que el registro A de $DOMINIO apunta a este servidor."
  sed -e "s|__DOMINIO__|$DOMINIO|g" -e "s|__WEB__|$WEB|g" -e "s|__ACME__|$ACME|g" "$REPO/deploy/nginx-https.conf" > /etc/nginx/sites-available/newtimes
  nginx -t -q && systemctl reload nginx
fi
ok "HTTPS activo (se renueva solo)"

paso "8/8 Actualización automática cada 5 minutos"
install -m 644 "$REPO/deploy/newtimes-actualizar.service" /etc/systemd/system/
install -m 644 "$REPO/deploy/newtimes-actualizar.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable -q --now newtimes-actualizar.timer
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow OpenSSH >/dev/null; ufw allow 'Nginx Full' >/dev/null; ok "Cortafuegos: web y SSH permitidos"
fi
ok "Temporizador activo"

echo
printf '\033[1;32mLISTO.\033[0m https://%s ya sirve NewTimes.news.\n' "$DOMINIO"
echo "Ver últimas actualizaciones:  sudo journalctl -u newtimes-actualizar -n 30 --no-pager"
