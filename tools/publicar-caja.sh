#!/usr/bin/env bash
# Publica la caja en SourceForge. Es la vía de distribución beta: la oficial será Zenodo y el espejo
# de la universidad.
#
#   SF_USUARIO=usuario SF_PROYECTO=netseclab tools/publicar-caja.sh build/box/netseclab-0.3.0-vmware.tar.gz
#   ... --dry-run    enseña lo que haría, sin subir nada
#
# Requiere `rsync` y `ssh`, y tener la clave pública registrada en la cuenta de SourceForge. El
# fichero se verifica contra el SHA256SUMS de su carpeta antes de subirlo: si no coincide, no sale.
set -uo pipefail

SECO=0
ARTEFACTO=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) SECO=1 ;;
    -*) echo "error: opción desconocida $arg" >&2; exit 2 ;;
    *) ARTEFACTO="$arg" ;;
  esac
done

if [ -z "$ARTEFACTO" ]; then
  echo "uso: SF_USUARIO=<usuario> SF_PROYECTO=<proyecto> $0 <artefacto.tar.gz> [--dry-run]" >&2
  exit 2
fi
if [ ! -f "$ARTEFACTO" ]; then
  echo "error: no existe el artefacto $ARTEFACTO" >&2
  exit 2
fi

CARPETA="$(cd "$(dirname "$ARTEFACTO")" && pwd)"
NOMBRE="$(basename "$ARTEFACTO")"
[ -f "$CARPETA/SHA256SUMS" ] || { echo "error: falta $CARPETA/SHA256SUMS" >&2; exit 2; }

echo "== comprobando el checksum"
( cd "$CARPETA" && sha256sum -c SHA256SUMS --ignore-missing ) || {
  echo "error: el artefacto no coincide con su SHA256SUMS; no se sube" >&2
  exit 1
}

USUARIO="${SF_USUARIO:-}"
PROYECTO="${SF_PROYECTO:-}"
[ -n "$USUARIO" ] || { echo "error: falta SF_USUARIO (tu usuario de SourceForge)" >&2; exit 2; }
[ -n "$PROYECTO" ] || { echo "error: falta SF_PROYECTO (nombre del proyecto en SourceForge)" >&2; exit 2; }

VERSION="${VERSION:-$(printf '%s' "$NOMBRE" | sed -nE 's/^netseclab-(.+)\.tar\.gz$/\1/p')}"
if [ -z "$VERSION" ]; then
  echo "error: no sé deducir la versión de $NOMBRE; pasa VERSION=..." >&2
  exit 2
fi

DESTINO="frs.sourceforge.net:/home/frs/project/$PROYECTO/netseclab/$VERSION/"
URL="https://sourceforge.net/projects/$PROYECTO/files/netseclab/$VERSION/$NOMBRE/download"

echo "== destino"
echo "   $DESTINO"
echo "   $NOMBRE ($(du -h "$ARTEFACTO" | cut -f1))"

if [ "$SECO" -eq 1 ]; then
  echo "== simulación (no se sube nada)"
  rsync -avn -e ssh "$CARPETA/$NOMBRE" "$CARPETA/SHA256SUMS" "$USUARIO@$DESTINO"
  echo
  echo "cuando se suba de verdad, la descarga estará en:"
  echo "   $URL"
  exit 0
fi

echo "== subiendo (si el proyecto no existe, rsync fallará al crear la carpeta)"
rsync -avP -e ssh "$CARPETA/$NOMBRE" "$CARPETA/SHA256SUMS" "$USUARIO@$DESTINO" || {
  echo "error: la subida falló. Comprueba el usuario, el proyecto y la clave SSH en SourceForge" >&2
  exit 1
}

echo "== hecho"
echo "   descarga:  $URL"
echo "   recuerda actualizar el README y las notas del release con esta URL"
