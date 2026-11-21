#!/usr/bin/env bash
# Instala aria2 y configura makepkg para usarlo en las descargas http/https.
# Uso: sudo bash aria2-makepkg.sh

set -euo pipefail

CONF="/etc/makepkg.conf"
BACKUP="/etc/makepkg.conf.bak"

if [[ $EUID -ne 0 ]]; then
    echo "Ejecuta el script con sudo: sudo bash $0"
    exit 1
fi

if [[ ! -f "$CONF" ]]; then
    echo "No se encontró $CONF"
    exit 1
fi

echo "==> Instalando aria2..."
pacman -S --needed --noconfirm aria2

if grep -q "'https::/usr/bin/aria2c -UWget -s16 -x16 -k1M" "$CONF" && grep -q "'http::/usr/bin/aria2c -UWget -s16 -x16 -k1M" "$CONF"; then
    echo "==> makepkg.conf ya usa aria2c con 16 conexiones. Nada que cambiar."
    exit 0
fi

if [[ ! -f "$BACKUP" ]]; then
    cp "$CONF" "$BACKUP"
    echo "==> Copia de seguridad guardada en $BACKUP"
fi

echo "==> Actualizando DLAGENTS en $CONF..."
sed -i \
    -e "s|'http::[^']*'|'http::/usr/bin/aria2c -UWget -s16 -x16 -k1M %u -o %o'|" \
    -e "s|'https::[^']*'|'https::/usr/bin/aria2c -UWget -s16 -x16 -k1M %u -o %o'|" \
    "$CONF"

echo "==> Líneas resultantes:"
grep -nE "'https?::" "$CONF"

echo "==> Listo. Para revertir: sudo cp $BACKUP $CONF"
