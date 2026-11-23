#!/usr/bin/env bash
# Comprobaciones que se ejecutan DENTRO de la caja y que no puede hacer el CI: Incus de verdad,
# systemd de verdad y los ejercicios contra el laboratorio levantado.
#
#   bash comprobar-caja.sh                  # dentro de la caja, como usuario lab
#   WORK=build/box tools/probar-caja.sh     # desde el proyecto: la arranca y llama a esto
#
# Se ejecuta desde un fichero y no por stdin: `incus profile create` lee su YAML de la entrada
# estándar cuando no es un terminal, y se comería el resto del guion.
set -u

LAB="${LAB:-/opt/netseclab/lab/examples/example.net.yaml}"
EJERCICIO="${EJERCICIO:-/opt/netseclab/lab/exercises/01-reconocimiento.yaml}"
PASS=0
FAIL=0

ok()   { PASS=$((PASS + 1)); printf '  [OK]   %s\n' "$*"; }
mal()  { FAIL=$((FAIL + 1)); printf '  [FALLO] %s\n' "$*"; }
paso() { printf '\n=== %s\n' "$*"; }

# comprobar <descripción> <código de salida esperado> -- comando...
comprobar() {
  local desc="$1" esperado="$2"
  shift 3
  local salida codigo
  salida="$("$@" 2>&1)"
  codigo=$?
  if [ "$codigo" -eq "$esperado" ]; then
    ok "$desc (exit $codigo)"
    printf '%s\n' "$salida" | tail -3 | sed 's/^/         /'
  else
    mal "$desc (exit $codigo, se esperaba $esperado)"
    printf '%s\n' "$salida" | tail -8 | sed 's/^/         /'
  fi
}

paso "versión y ayuda"
comprobar "lab --version" 0 -- sh -c 'lab --version | grep -q "netseclab" && lab --version'
comprobar "lab --help lista los comandos" 0 -- sh -c 'lab --help | grep -q "unpack"'

paso "levantar el laboratorio (7 nodos, perfil full)"
lab up "$LAB" --profile full > /tmp/up.log 2>&1
if grep -q "steps run" /tmp/up.log; then
  ok "lab up: $(grep 'steps run' /tmp/up.log)"
else
  mal "lab up no terminó"
  tail -20 /tmp/up.log | sed 's/^/         /'
fi

paso "reiniciar: lab down y volver a subir"
comprobar "lab down para el laboratorio entero" 0 -- sh -c 'lab down '"$LAB"' --profile full >/dev/null'
comprobar "lab up arranca los nodos que ya existen" 0 -- \
  sh -c 'lab up '"$LAB"' --profile full | grep -q "steps run"'

paso "estado, rutas y cortafuegos"
comprobar "lab status ve los 7 nodos en marcha" 0 -- \
  sh -c 'test "$(lab status | grep -c "Running")" -eq 7'
comprobar "exta tiene ruta a la DMZ" 0 -- \
  sh -c 'incus exec exta -- ip -4 route | grep -q "10.5.1.0/24 via 10.5.0.254"'
comprobar "exta tiene ruta a la interna" 0 -- \
  sh -c 'incus exec exta -- ip -4 route | grep -q "10.5.2.0/24 via 10.5.0.254"'
comprobar "nmap desde exta: 80 abierto" 0 -- \
  sh -c 'incus exec exta -- nmap -Pn -p22,80,443 www.example.net | grep -q "80/tcp *open"'
comprobar "nmap desde exta: 443 cerrado" 0 -- \
  sh -c 'incus exec exta -- nmap -Pn -p22,80,443 www.example.net | grep -q "443/tcp *closed"'
comprobar "nmap desde exta: 22 filtrado" 0 -- \
  sh -c 'incus exec exta -- nmap -Pn -p22,80,443 www.example.net | grep -q "22/tcp *filtered"'
comprobar "los nombres resuelven por el DNS del laboratorio" 0 -- \
  sh -c 'incus exec exta -- getent hosts www.example.net | grep -q 10.5.1.10'

paso "ejercicio de reconocimiento"
comprobar "lab check pasa los hechos del entorno" 0 -- \
  sh -c 'lab check '"$EJERCICIO"' | grep -q "3/3 environment checks"'
comprobar "lab answer acepta 443" 0 -- lab answer "$EJERCICIO" puerto-cerrado 443
comprobar "lab check da 5/5" 0 -- sh -c 'lab check '"$EJERCICIO"' | grep -q "5/5 points"'
comprobar "lab report escribe el informe" 0 -- \
  lab report "$EJERCICIO" --out /tmp/informe.md

paso "captura, snapshot y reset"
comprobar "lab capture escribe un pcap" 0 -- \
  sh -c 'sudo lab capture '"$LAB"' --net dmz --seconds 5 --out /tmp/cap.pcap >/dev/null 2>&1 &&
         test -s /tmp/cap.pcap'
comprobar "lab snapshot toma la foto" 0 -- lab snapshot "$LAB" --name prueba
comprobar "lab reset vuelve al snapshot inicial" 0 -- lab reset "$LAB" --name initial

paso "paquetes de laboratorio: empaquetar, firmar, verificar"
mkdir -p /tmp/pack
ssh-keygen -q -t ed25519 -N "" -f /tmp/prof -C "profesor@universidad" 2>/dev/null
cd /opt/netseclab || exit 1
comprobar "lab pack --sign crea paquete y firma" 0 -- sh -c \
  'lab pack lab/examples/example.net.yaml --out /tmp/pack/e.net.labpack --sign /tmp/prof &&
   test -s /tmp/pack/e.net.labpack && test -s /tmp/pack/e.net.labpack.sig'
comprobar "lab unpack --signer verifica y extrae" 0 -- sh -c \
  'lab unpack /tmp/pack/e.net.labpack --to /tmp/pack/extraido --signer /tmp/prof.pub |
   grep -q "signature ok"'
comprobar "lab unpack rechaza una firma ajena" 2 -- sh -c \
  'ssh-keygen -q -t ed25519 -N "" -f /tmp/otro 2>/dev/null;
   lab unpack /tmp/pack/e.net.labpack --to /tmp/pack/ajeno --signer /tmp/otro.pub'

paso "entornos: lock"
cat > /tmp/env.yaml <<'YAML'
version: 1
name: envlab
networks:
  n1: { cidr: 10.9.0.0/24, type: isolated, mode: switch }
nodes:
  - name: srv
    environment:
      base: debian13
      packages: [tcpdump]
    links: [{ net: n1, ip: 10.9.0.1 }]
YAML
comprobar "lab lock escribe el lock" 0 -- lab lock /tmp/env.yaml --out /tmp/env.lock
comprobar "lab lock --check no ve deriva" 0 -- lab lock /tmp/env.yaml --out /tmp/env.lock --check

paso "caché de imágenes: gc, push y pull"
comprobar "lab gc no borra las imágenes en uso" 0 -- \
  sh -c 'lab gc '"$LAB"' --yes >/dev/null &&
         incus image info lab-node-v1 >/dev/null 2>&1 &&
         incus image info lab-web-v1 >/dev/null 2>&1'
comprobar "lab push exporta la imagen al bucket" 0 -- \
  sh -c 'mkdir -p /tmp/bucket && lab push lab-node-v1 --to /tmp/bucket | grep -q "lab-node-v1"'
comprobar "lab pull la importa verificando el sha256" 0 -- \
  sh -c 'lab pull lab-node-v1 --from /tmp/bucket --as node-base | grep -q "sha256 verified"'

paso "consola web"
( lab web --port 8099 --token prueba > /tmp/web.log 2>&1 & echo $! > /tmp/web.pid )
sleep 3
comprobar "lab web responde con el token" 0 -- \
  sh -c 'curl -fsS -o /dev/null "http://127.0.0.1:8099/?token=prueba"'
comprobar "lab web rechaza sin el token" 0 -- \
  sh -c 'test "$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8099/)" = 401'
kill "$(cat /tmp/web.pid)" 2>/dev/null

paso "apagar y limpiar"
comprobar "lab down para el laboratorio" 0 -- lab down "$LAB" --profile full
comprobar "el disco queda holgado" 0 -- \
  sh -c 'test "$(df --output=pcent / | tail -1 | tr -dc 0-9)" -lt 70'

printf '\n=== RESULTADO: %d ok, %d fallos\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
