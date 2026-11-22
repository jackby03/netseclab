#!/usr/bin/env bash
# Construye la caja: una VM Debian 13 mínima con Incus, el CLI y las imágenes cacheadas.
#
# Necesita un anfitrión Linux x86_64 con qemu-system-x86_64, qemu-img, ssh, curl y python3.
# No necesita root si se usa aceleración KVM con permisos correctos; sí lo necesita para /dev/kvm
# en la mayoría de distribuciones.
#
#   ./images/box/build.sh              # todo: imagen, provisión y VMDK
#   ./images/box/build.sh imagen       # solo construye y provisiona el qcow2
#   ./images/box/build.sh vmdk         # solo convierte a VMDK/VirtualBox
#
# El resultado queda en build/box/.
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAIZ="$(cd "$AQUI/../.." && pwd)"
WORK="${WORK:-$RAIZ/build/box}"

# Versión de Debian fijada: no se usa "latest" para que el build sea reproducible.
DEBIAN_BUILD="${DEBIAN_BUILD:-20261116-2664}"
BASE_URL="https://cloud.debian.org/images/cloud/trixie/${DEBIAN_BUILD}"
if [ "$DEBIAN_BUILD" = "latest" ]; then
  BASE_IMG="debian-13-genericcloud-amd64.qcow2"
else
  # En los directorios de un build concreto el nombre incluye el identificador.
  BASE_IMG="debian-13-genericcloud-amd64-${DEBIAN_BUILD}.qcow2"
fi
DISCO="$WORK/netseclab.qcow2"
PUERTO_HTTP="${PUERTO_HTTP:-8765}"
PUERTO_SSH="${PUERTO_SSH:-2222}"
CLAVE="$WORK/id_ed25519"

# Opciones comunes. El puerto se pasa aparte porque ssh usa -p y scp usa -P.
SSH_OPTS=(-i "$CLAVE" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
          -o LogLevel=ERROR)

ssh_vm()  { ssh "${SSH_OPTS[@]}" -p "$PUERTO_SSH" "$@"; }
scp_vm()  { scp "${SSH_OPTS[@]}" -P "$PUERTO_SSH" "$@"; }

log()  { printf '\033[1;34m==\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || fail "falta el programa '$1'"; }

comprobar_entorno() {
  need qemu-system-x86_64
  need qemu-img
  need ssh
  need scp
  need curl
  need python3
  need tar
  [ "$(uname -s)" = "Linux" ] || fail "la construcción necesita Linux (usa WSL2 si estás en Windows)"
  mkdir -p "$WORK"
}

descargar_base() {
  # una descarga fallida deja un fichero vacío: no vale como "ya descargada"
  if [ -f "$WORK/$BASE_IMG" ] && [ "$(stat -c%s "$WORK/$BASE_IMG")" -gt 100000000 ]; then
    log "imagen base ya descargada"
    return
  fi
  log "descargando $BASE_IMG ($DEBIAN_BUILD)"
  curl -fL --progress-bar -o "$WORK/$BASE_IMG" "$BASE_URL/$BASE_IMG" || fail \
    "no se pudo descargar $BASE_URL/$BASE_IMG
  Comprueba qué builds existen en https://cloud.debian.org/images/cloud/trixie/
  y pásalo con DEBIAN_BUILD=<build> (o DEBIAN_BUILD=latest)."
  curl -fsSL -o "$WORK/SHA512SUMS" "$BASE_URL/SHA512SUMS" \
    || fail "no se pudo descargar el SHA512SUMS de $BASE_URL"
  ( cd "$WORK" && grep " $BASE_IMG\$" SHA512SUMS | sha512sum -c - ) \
    || fail "la imagen base no coincide con su checksum"
}

preparar_disco() {
  [ -f "$DISCO" ] && return
  log "creando el disco de la caja (12 GB, overlay sobre la imagen cloud)"
  qemu-img create -q -f qcow2 -F qcow2 -b "$WORK/$BASE_IMG" "$DISCO" 12G
}

preparar_semilla() {
  [ -f "$CLAVE" ] || ssh-keygen -q -t ed25519 -N "" -f "$CLAVE"
  local pub; pub="$(cat "$CLAVE.pub")"
  rm -rf "$WORK/seed"
  cp -r "$AQUI/seed" "$WORK/seed"
  python3 - "$WORK/seed/user-data" "$pub" <<'PY'
import sys, pathlib
ruta, clave = sys.argv[1], sys.argv[2]
p = pathlib.Path(ruta)
p.write_text(p.read_text().replace("__PUBKEY__", clave), encoding="utf-8")
PY
}

aceleracion() {
  # Con /dev/kvm utilizable la construcción vuela; sin él QEMU emula y tarda mucho más.
  if [ -w /dev/kvm ] && qemu-system-x86_64 -accel help 2>/dev/null | grep -qw kvm; then
    echo "-accel kvm -cpu host"
  else
    echo "-accel tcg -cpu max"
  fi
}

arrancar() {
  # Si quedó una VM de un intento anterior, se apaga con educación: matarla a lo
  # bruto deja el ext4 sucio y luego se monta en solo lectura.
  if [ -f "$WORK/qemu.pid" ] && kill -0 "$(cat "$WORK/qemu.pid")" 2>/dev/null; then
    log "la VM del intento anterior sigue en marcha: apagándola"
    ssh_vm lab@127.0.0.1 'sudo poweroff' 2>/dev/null || true
    for _ in $(seq 1 60); do
      kill -0 "$(cat "$WORK/qemu.pid")" 2>/dev/null || break
      sleep 1
    done
    kill "$(cat "$WORK/qemu.pid")" 2>/dev/null || true
    sleep 1
  fi

  log "sirviendo la semilla en 127.0.0.1:$PUERTO_HTTP"
  ( cd "$WORK/seed" && python3 -m http.server "$PUERTO_HTTP" --bind 127.0.0.1 >/dev/null 2>&1 ) &
  echo $! > "$WORK/http.pid"

  local accel; accel="$(aceleracion)"
  if [ "$accel" = "-accel tcg -cpu max" ]; then
    log "AVISO: sin /dev/kvm, QEMU emulará la CPU y la construcción tardará bastante más"
  fi
  log "arrancando la VM ($accel)"
  # $accel se expande a propósito sin comillas: son dos argumentos
  qemu-system-x86_64 \
    $accel -machine q35 -smp 2 -m 2048 \
    -drive file="$DISCO",if=virtio,format=qcow2 \
    -netdev user,id=n0,hostfwd=tcp:127.0.0.1:"$PUERTO_SSH"-:22 \
    -device virtio-net-pci,netdev=n0 \
    -smbios "type=1,serial=ds=nocloud;s=http://10.0.2.2:$PUERTO_HTTP/" \
    -display none -serial "file:$WORK/serial.log" \
    -daemonize -pidfile "$WORK/qemu.pid"
}

esperar_ssh() {
  local segundos="${TIMEOUT_SSH:-600}"
  log "esperando a que la VM acepte SSH (hasta $((segundos / 60)) minutos)"
  for _ in $(seq 1 $((segundos / 2))); do
    if ssh_vm lab@127.0.0.1 true 2>/dev/null; then
      return 0
    fi
    sleep 2
  done
  fail "la VM no respondió; mira $WORK/serial.log"
}

provisionar() {
  log "copiando el proyecto y provisionando"
  tar -C "$RAIZ" -czf "$WORK/netseclab-src.tar.gz" \
      --exclude=build --exclude=.git --exclude=__pycache__ --exclude=research \
      pyproject.toml src lab docs README.md
  scp_vm -q "$WORK/netseclab-src.tar.gz" lab@127.0.0.1:/tmp/
  scp_vm -q "$AQUI/provision.sh" lab@127.0.0.1:/tmp/netseclab-provision.sh
  # Se ejecuta desde un fichero, no por stdin: así ningún comando de dentro
  # (incus, apt) puede consumir el resto del script.
  ssh_vm lab@127.0.0.1 'sudo bash /tmp/netseclab-provision.sh'
}

apagar() {
  log "apagando la caja"
  ssh_vm lab@127.0.0.1 'sudo poweroff' 2>/dev/null || true
  for _ in $(seq 1 60); do
    [ -f "$WORK/qemu.pid" ] || break
    kill -0 "$(cat "$WORK/qemu.pid")" 2>/dev/null || break
    sleep 1
  done
  [ -f "$WORK/http.pid" ] && kill "$(cat "$WORK/http.pid")" 2>/dev/null || true
}

exportar_vmdk() {
  log "convirtiendo a VMDK (streamOptimized)"
  qemu-img convert -q -p -O vmdk -o subformat=streamOptimized \
    "$DISCO" "$WORK/netseclab.vmdk"
  cp "$AQUI/netseclab.vmx" "$WORK/netseclab.vmx"
  ( cd "$WORK" && tar -czf netseclab-vmware.tar.gz netseclab.vmx netseclab.vmdk )
  log "listo: $WORK/netseclab-vmware.tar.gz"
  log "en VMware: descomprime y abre netseclab.vmx"
}

todo() {
  comprobar_entorno
  descargar_base
  preparar_disco
  preparar_semilla
  arrancar
  esperar_ssh
  provisionar
  apagar
  exportar_vmdk
}

case "${1:-todo}" in
  todo)      todo ;;
  imagen)    comprobar_entorno; descargar_base; preparar_disco; preparar_semilla; arrancar; esperar_ssh; provisionar; apagar ;;
  vmdk)      comprobar_entorno; exportar_vmdk ;;
  *)         echo "uso: $0 [todo|imagen|vmdk]" >&2; exit 2 ;;
esac
