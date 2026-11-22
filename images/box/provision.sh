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
  python3 python3-yaml openssh-server

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

echo "== imágenes base cacheadas"
# Arrancar y borrar una instancia deja la imagen en la caché local: luego funciona sin red.
if ! incus image list --format csv 2>/dev/null | grep -q .; then
  incus launch images:debian/13 warmup
  incus delete warmup --force
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
