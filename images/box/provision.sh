#!/usr/bin/env bash
# Provisionamiento de la caja. Se ejecuta DENTRO de la VM recién arrancada.
#
# Deja un Debian mínimo con Incus, el CLI del laboratorio y las imágenes base cacheadas, listo para
# funcionar sin Internet.
set -euo pipefail

# Este script se ejecuta desde un fichero, no por stdin, así que puede cerrar la entrada:
# ningún comando de dentro (incus, apt) debe quedarse leyendo del canal de SSH.
exec < /dev/null

export DEBIAN_FRONTEND=noninteractive

# cloud-init también toca apt al primer arranque. Si empezamos a la vez, chocamos
# por el lock de /var/lib/apt/lists.
echo "== esperando a cloud-init"
cloud-init status --wait >/dev/null 2>&1 || true

apt_update() {
  local intentos=0
  until apt-get update -qq; do
    intentos=$((intentos + 1))
    if [ "$intentos" -ge 5 ]; then
      echo "error: apt-get update no consigue el lock"
      return 1
    fi
    echo "  apt ocupado, reintentando en 5 s ($intentos/5)"
    sleep 5
  done
}

apt_install() {
  local intentos=0
  until DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$@"; do
    intentos=$((intentos + 1))
    if [ "$intentos" -ge 5 ]; then
      echo "error: no se pudieron instalar los paquetes"
      return 1
    fi
    echo "  apt ocupado, reintentando en 5 s ($intentos/5)"
    sleep 5
  done
}

echo "== paquetes base"
apt_update
apt_install \
  incus openvswitch-switch bridge-utils \
  tcpdump curl jq ca-certificates \
  python3 python3-yaml openssh-server \
  open-vm-tools

echo "== incus"
systemctl enable --now incus.socket incus.service

echo "== esperando al demonio de incus"
for _ in $(seq 1 60); do
  incus version >/dev/null 2>&1 && break
  sleep 1
done
incus version >/dev/null 2>&1 || { echo "error: el demonio de incus no responde"; exit 1; }

if ! incus storage list --format csv 2>/dev/null | grep -q .; then
  echo "== inicializando incus"
  incus admin init --auto
fi
if ! incus storage list --format csv 2>/dev/null | grep -q .; then
  echo "error: no se pudo crear el pool de almacenamiento"
  exit 1
fi

echo "== perfil para los nodos del laboratorio"
# El disco raíz lo aporta un perfil. El perfil por defecto trae además una tarjeta
# en incusbr0 que no queremos en los nodos, así que hacemos uno a medida.
if ! incus profile show netseclab >/dev/null 2>&1; then
  incus profile create netseclab
  incus profile device add netseclab root disk path=/ pool=default
fi

echo "== imágenes de nodo, con lo imprescindible dentro"
# El laboratorio tiene que funcionar sin Internet, así que los nodos no pueden
# instalar nada al arrancar: la imagen ya trae las herramientas comunes.
imagen_existe() {
  incus image list --format csv -c aliases 2>/dev/null | grep -q "$1"
}

if ! imagen_existe "lab-node-v1"; then
  incus launch images:debian/13 proto-node
  incus exec proto-node -- sh -c \
    'apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
       openssh-server iproute2 nftables curl jq tcpdump nmap rsyslog isc-dhcp-client'
  incus stop proto-node
  incus publish proto-node --alias lab-node-v1
  incus delete proto-node --force
fi

if ! imagen_existe "lab-web-v1"; then
  incus launch lab-node-v1 proto-web
  incus exec proto-web -- sh -c \
    'apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
       apache2 php libapache2-mod-php'
  incus exec proto-web -- sh -c 'a2enmod php8.4 >/dev/null 2>&1 || true; systemctl enable apache2'
  incus stop proto-web
  incus publish proto-web --alias lab-web-v1
  incus delete proto-web --force
fi

if ! imagen_existe "lab-ids-v1"; then
  incus launch lab-node-v1 proto-ids
  incus exec proto-ids -- sh -c \
    'apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq suricata'
  incus stop proto-ids
  incus publish proto-ids --alias lab-ids-v1
  incus delete proto-ids --force
fi

if ! imagen_existe "lab-attacker-v1"; then
  incus launch lab-node-v1 proto-attacker
  incus exec proto-attacker -- sh -c \
    'apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
       masscan whatweb ffuf gobuster nikto dirb tshark tcpflow'
  incus stop proto-attacker
  incus publish proto-attacker --alias lab-attacker-v1
  incus delete proto-attacker --force
fi

echo "== paquetes de los toolsets, para poder instalarlos sin Internet"
TOOLSETS="nmap masscan dnsutils whatweb whois curl ffuf gobuster nikto dirb jq \
tcpdump tshark bettercap mitmproxy tcpflow hydra john medusa openssl sslscan \
auditd aide fail2ban lynis rkhunter hping3 python3-scapy iperf3 tcpreplay dsniff \
sqlmap wfuzz apache2 php libapache2-mod-php nftables suricata"
apt-get install -y -qq --download-only ${TOOLSETS} || true

echo "== CLI del laboratorio"
install -d /opt/netseclab
tar -C /opt/netseclab -xzf /tmp/netseclab-src.tar.gz
cat > /usr/local/bin/lab <<'WRAPPER'
#!/bin/sh
# Lanzador del CLI. Sin instalación: el paquete vive en /opt/netseclab.
PYTHONPATH=/opt/netseclab/src${PYTHONPATH:+:$PYTHONPATH} exec python3 -m lab.cli "$@"
WRAPPER
chmod 0755 /usr/local/bin/lab

echo "== claves SSH de host: se generan en el primer arranque del alumno"
rm -f /etc/ssh/ssh_host_*
cat > /etc/systemd/system/lab-ssh-keys.service <<'UNIT'
[Unit]
Description=Genera las claves SSH de host en el primer arranque
Before=ssh.service
ConditionPathExists=!/etc/ssh/ssh_host_ed25519_key

[Service]
Type=oneshot
ExecStart=/usr/bin/ssh-keygen -A

[Install]
WantedBy=multi-user.target
UNIT
systemctl enable lab-ssh-keys.service

echo "== red de gestión, independiente de cloud-init"
# cloud-init configuró la interfaz del build (la de QEMU); en VMware la interfaz
# se llama de otra forma. Un servicio propio pide DHCP en todas las que haya.
apt_install isc-dhcp-client
cat > /etc/systemd/system/lab-mgmt-net.service <<'UNIT'
[Unit]
Description=DHCP en las interfaces de gestión
After=network-pre.target
Before=network.target
Wants=network-pre.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c 'for p in /sys/class/net/*; do i=$(basename "$p"); [ "$i" = lo ] && continue; dhclient -1 "$i" || true; done'

[Install]
WantedBy=multi-user.target
UNIT
systemctl enable lab-mgmt-net.service
# la configuración de cloud-init apuntaba a la interfaz del build: no molesta, pero sobra
rm -f /etc/network/interfaces.d/50-cloud-init /etc/network/interfaces.d/50-cloud-init.cfg

echo "== limpieza para distribuir"
# NO se hace `apt-get clean`: la caché de .deb es lo que permite instalar las
# herramientas de cada ejercicio sin Internet. Solo se limpian las listas.
rm -rf /var/lib/apt/lists/*
cloud-init clean --logs --seed || true
truncate -s 0 /etc/machine-id
rm -rf /var/lib/cloud/* /root/.bash_history /home/lab/.bash_history
# la caja no usa cloud-init en tiempo de ejecución: su configuración la lleva el CLI
touch /etc/cloud/cloud-init.disabled
rm -f /tmp/netseclab-src.tar.gz

sync
echo "== provisionamiento terminado"
