#!/usr/bin/env bash
# Prueba la caja construida: la arranca en QEMU con un overlay desechable, entra por SSH y ejecuta
# las comprobaciones de `tools/comprobar-caja.sh` dentro de la VM.
#
# El overlay se borra al terminar: el disco que se publica no queda tocado por las pruebas.
#
#   WORK=build/box tools/probar-caja.sh     # build/box es el valor por defecto
#
# Necesita Linux con KVM y qemu; en Windows, ejecútalo dentro de WSL.
set -uo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAIZ="$(cd "$AQUI/.." && pwd)"
WORK="${WORK:-$RAIZ/build/box}"
DISCO="$WORK/netseclab.qcow2"
CLAVE="$WORK/id_ed25519"
PUERTO="${PUERTO:-2222}"
OVERLAY="$WORK/prueba-overlay.qcow2"
SERIAL="$WORK/prueba-serial.log"
PIDFILE="$WORK/prueba.pid"

fallar() { printf 'error: %s\n' "$*" >&2; exit 2; }

[ -f "$DISCO" ] || fallar "no existe $DISCO; construye la caja con make box"
[ -f "$CLAVE" ] || fallar "no existe $CLAVE; debería haberlo generado la construcción"
command -v qemu-system-x86_64 >/dev/null 2>&1 || fallar "falta qemu-system-x86_64"

SSH=(ssh -i "$CLAVE" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
     -o LogLevel=ERROR -p "$PUERTO" lab@127.0.0.1)
SCP=(scp -i "$CLAVE" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
     -o LogLevel=ERROR -P "$PUERTO")

arrancada=0
apagar() {
  if [ "$arrancada" -eq 1 ]; then
    "${SSH[@]}" 'sudo poweroff' >/dev/null 2>&1 || true
    # QEMU borra su propio pidfile al salir; se lee una vez y se tolera que ya no esté.
    pid="$(cat "$PIDFILE" 2>/dev/null || true)"
    if [ -n "$pid" ]; then
      for _ in $(seq 1 30); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 1
      done
      kill "$pid" 2>/dev/null || true
    fi
    arrancada=0
  fi
  rm -f "$OVERLAY" "$PIDFILE"
}
trap apagar EXIT

# Si quedó una VM de una pasada anterior, se apaga antes de usar el puerto.
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  apagar
fi

rm -f "$OVERLAY" "$SERIAL"
qemu-img create -q -f qcow2 -F qcow2 -b "$DISCO" "$OVERLAY"
qemu-system-x86_64 \
  -accel kvm -cpu host -machine q35 -smp 2 -m 2048 \
  -drive file="$OVERLAY",if=virtio,format=qcow2,discard=unmap \
  -netdev user,id=n0,hostfwd=tcp:127.0.0.1:"$PUERTO"-:22 \
  -device virtio-net-pci,netdev=n0 \
  -display none -serial "file:$SERIAL" \
  -daemonize -pidfile "$PIDFILE"
arrancada=1
echo "VM arrancada con $DISCO"

echo "esperando a SSH"
for _ in $(seq 1 90); do
  "${SSH[@]}" true 2>/dev/null && break
  sleep 2
done
"${SSH[@]}" true 2>/dev/null || fallar "la caja no respondió; mira $SERIAL"

"${SCP[@]}" -q "$AQUI/comprobar-caja.sh" lab@127.0.0.1:/tmp/comprobar-caja.sh
echo "comprobando dentro de la caja"
"${SSH[@]}" 'bash /tmp/comprobar-caja.sh'
estado=$?
exit "$estado"
