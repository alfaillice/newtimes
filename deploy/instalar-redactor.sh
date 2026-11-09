#!/usr/bin/env bash
# Instala el redactor automático en el servidor (ejecutar después de instalar.sh).
# Uso:  sudo bash /srv/newtimes/repo/deploy/instalar-redactor.sh
# Se puede ejecutar varias veces.
set -euo pipefail
USUARIO="newtimes"
DIR="/srv/newtimes/redactor"
REPO_SSH="git@github.com:alfaillice/newtimes.git"
ENV="/etc/newtimes/redactor.env"
[ "$(id -u)" -eq 0 ] || { echo "Ejecútalo con sudo"; exit 1; }

# Carpeta personal real del usuario: puede no existir si el usuario es anterior al instalador
CASA="$(getent passwd "$USUARIO" | cut -d: -f6)"
if [ -z "$CASA" ] || [ "$CASA" = "/nonexistent" ]; then
  CASA="/home/$USUARIO"
  usermod -d "$CASA" "$USUARIO"
fi
[ -d "$CASA" ] || install -d -o "$USUARIO" -g "$USUARIO" -m 755 "$CASA"
install -d -o "$USUARIO" -g "$USUARIO" -m 700 "$CASA/.ssh"
CLAVE="$CASA/.ssh/id_redactor"

echo "==> 1/4 Clave de API"
mkdir -p /etc/newtimes
if [ ! -f "$ENV" ]; then
  read -rsp "Pega tu ANTHROPIC_API_KEY (de console.anthropic.com) y pulsa Intro: " K; echo
  printf 'ANTHROPIC_API_KEY=%s\nNEWTIMES_MODELO=claude-haiku-5-5\nNEWTIMES_MAX=2\n' "$K" > "$ENV"
fi
chown root:"$USUARIO" "$ENV"; chmod 640 "$ENV"

echo "==> 2/4 Clave SSH con permiso de escritura en GitHub"
if [ ! -f "$CLAVE" ]; then
  sudo -u "$USUARIO" ssh-keygen -q -t ed25519 -N "" -C "newtimes-redactor-escritura" -f "$CLAVE"
fi
sudo -u "$USUARIO" sh -c "ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null; sort -u -o ~/.ssh/known_hosts ~/.ssh/known_hosts"
export GIT_SSH_COMMAND="ssh -i $CLAVE -o IdentitiesOnly=yes"
if ! sudo -u "$USUARIO" GIT_SSH_COMMAND="$GIT_SSH_COMMAND" git ls-remote "$REPO_SSH" >/dev/null 2>&1; then
  echo
  echo "Añade esta clave en GitHub > alfaillice/newtimes > Settings > Deploy keys > Add deploy key"
  echo "y MARCA 'Allow write access':"
  echo; cat "$CLAVE.pub"; echo
  read -rp "Pulsa Intro cuando la hayas añadido... " _
fi

echo "==> 3/4 Copia de trabajo del redactor"
if [ ! -d "$DIR/.git" ]; then
  sudo -u "$USUARIO" GIT_SSH_COMMAND="$GIT_SSH_COMMAND" git clone -q "$REPO_SSH" "$DIR"
fi
sudo -u "$USUARIO" git -C "$DIR" config core.sshCommand "$GIT_SSH_COMMAND"
sudo -u "$USUARIO" git -C "$DIR" config user.name "NewTimes Redactor"
sudo -u "$USUARIO" git -C "$DIR" config user.email "redaccion@newtimes.news"
sudo -u "$USUARIO" git -C "$DIR" pull -q --rebase origin main

echo "==> 4/4 Temporizador"
for u in newtimes-redactor newtimes-redactor-en newtimes-encargos newtimes-titulares newtimes-salud; do
  install -m 644 "$DIR/deploy/$u.service" /etc/systemd/system/
  install -m 644 "$DIR/deploy/$u.timer" /etc/systemd/system/
done
touch /srv/newtimes/.redactor.lock; chown "$USUARIO":"$USUARIO" /srv/newtimes/.redactor.lock
systemctl daemon-reload
systemctl enable -q --now newtimes-redactor.timer newtimes-redactor-en.timer newtimes-encargos.timer newtimes-titulares.timer newtimes-salud.timer
echo
echo "Listo (español a las :20 de cada hora; inglés a las :35; encargos cada 5 min; titulares 5 veces al día; informe de salud SEO a las 23:30). Prueba sin publicar:"
echo "  sudo -u $USUARIO env \$(cat $ENV | xargs) python3 $DIR/redaccion/servidor/redactor.py --prueba"
echo "  sudo -u $USUARIO env \$(cat $ENV | xargs) python3 $DIR/redaccion/servidor/redactor.py --prueba --edicion en"
echo "Ver el registro:  journalctl -u newtimes-redactor -n 50   |   journalctl -u newtimes-redactor-en -n 50   |   journalctl -u newtimes-encargos -n 50"
