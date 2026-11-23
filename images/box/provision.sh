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
# incus-base es el demonio de Incus solo para contenedores: no arrastra QEMU,
# swtpm ni virtiofsd, que son para máquinas virtuales y aquí no se usan. Eso son
# cientos de megas menos de descarga y de imagen.
apt_install \
  incus-base openvswitch-switch bridge-utils \
  tcpdump curl jq ca-certificates \
  python3 python3-yaml openssh-server \
  open-vm-tools btrfs-progs

echo "== incus"
systemctl enable --now incus.socket incus.service

# El demonio de Incus solo habla con root y con el grupo dueño de su socket. El
# usuario `lab` se creó antes de instalar Incus, así que hay que añadirlo a mano
# o `lab up` falla con "You don't have the needed permissions to talk to the
# incus daemon". El nombre del grupo se lee del socket: no todos los paquetes lo
# llaman igual.
GRUPO_INCUS="$(stat -c '%G' /var/lib/incus/unix.socket 2>/dev/null || true)"
if [ -n "$GRUPO_INCUS" ] && [ "$GRUPO_INCUS" != "root" ]; then
  usermod -aG "$GRUPO_INCUS" lab && echo "  usuario lab añadido al grupo $GRUPO_INCUS"
else
  for grupo in incus-admin incus; do
    if getent group "$grupo" >/dev/null 2>&1; then
      usermod -aG "$grupo" lab && echo "  usuario lab añadido al grupo $grupo"
    fi
  done
fi

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

echo "== almacenamiento copy-on-write"
# El pool por defecto (`dir`) copia la imagen completa para cada contenedor:
# siete nodos de ~1,2 GB llenan un disco de 12 GB. Con btrfs sobre un fichero
# los nodos comparten bloques con la imagen y ocupan decenas de megas.
if apt-get install -y -qq btrfs-progs >/dev/null 2>&1; then
  # Con `size` y sin `source`, Incus crea él mismo el fichero del pool. Pasar
  # `source` apuntando a un fichero propio no está permitido.
  if incus storage create labpool btrfs size=8GiB >/dev/null 2>&1; then
    incus profile device set default root pool=labpool >/dev/null 2>&1 || true
    echo "  pool btrfs: los nodos comparten bloques con la imagen"
  else
    echo "  aviso: no se pudo crear el pool btrfs; se sigue con el de directorios"
  fi
else
  echo "  aviso: no hay btrfs-progs; se sigue con el pool de directorios"
fi

echo "== perfil para los nodos del laboratorio"
# El disco raíz lo aporta un perfil. El perfil por defecto trae además una tarjeta
# en incusbr0 que no queremos en los nodos, así que hacemos uno a medida. El pool
# se toma del perfil por defecto: si es btrfs, los nodos comparten bloques; si el
# pool btrfs no se pudo crear, sigue funcionando con el de directorios.
if ! incus profile show netseclab >/dev/null 2>&1; then
  incus profile create netseclab
  POOL_NODOS="$(incus profile device get default root pool 2>/dev/null || echo default)"
  incus profile device add netseclab root disk path=/ "pool=$POOL_NODOS"
  echo "  perfil netseclab sobre el pool $POOL_NODOS"
fi

echo "== imágenes de nodo, con lo imprescindible dentro"
# El laboratorio tiene que funcionar sin Internet, así que los nodos no pueden
# instalar nada al arrancar: la imagen ya trae las herramientas comunes.
imagen_existe() {
  # `incus image info <alias>` resuelve el alias si existe; es más fiable que
  # filtrar el listado, cuyo formato CSV cambia entre versiones.
  incus image info "$1" >/dev/null 2>&1
}

# Un paquete que no exista en los repositorios no puede tumbar la construcción:
# se instala lo que haya y se avisa de lo que falte.
instalar() {
  local inst="$1" paquetes="$2"
  if incus exec "$inst" -- sh -c \
      "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $paquetes"; then
    return 0
  fi
  echo "  aviso: algún paquete no está disponible; se instala uno a uno"
  for p in $paquetes; do
    incus exec "$inst" -- sh -c \
      "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $p" \
      || echo "  aviso: paquete no disponible en esta Debian: $p"
  done
}

construir_imagen() {
  local nombre="$1" base="$2" paquetes="$3" extra="${4:-}"
  # Los restos de un intento anterior estorban: se borran antes de empezar.
  incus delete "proto-$nombre" --force >/dev/null 2>&1 || true
  incus launch "$base" "proto-$nombre"
  incus exec "proto-$nombre" -- sh -c 'apt-get update -qq' || true
  instalar "proto-$nombre" "$paquetes"
  if [ -n "$extra" ]; then
    incus exec "proto-$nombre" -- sh -c "$extra"
  fi
  incus stop "proto-$nombre"
  # Si el alias se quedó de un intento a medias, se retira para poder publicar.
  incus image alias delete "lab-$nombre-v1" >/dev/null 2>&1 || true
  incus publish "proto-$nombre" --alias "lab-$nombre-v1"
  incus delete "proto-$nombre" --force
}

if ! imagen_existe "lab-node-v1"; then
  # dnsmasq lo necesita cualquier nodo que sirva DHCP o DNS en un escenario.
  # Las credenciales son las mismas que en la caja: root y user1, con netseclab.
  # Y el prompt de login recuerda cómo salir de la consola, que no es evidente.
  construir_imagen node images:debian/13 \
    "openssh-server iproute2 nftables curl jq tcpdump nmap rsyslog isc-dhcp-client dnsmasq" \
    'echo "root:netseclab" | chpasswd; \
     id user1 >/dev/null 2>&1 || useradd -m -s /bin/bash -G sudo user1; \
     echo "user1:netseclab" | chpasswd; \
     sed -i "s/^#\?PasswordAuthentication.*/PasswordAuthentication yes/" /etc/ssh/sshd_config; \
     systemctl enable ssh; \
     echo "netseclab node - to leave the console: Ctrl-a then q" >> /etc/issue'
fi

if ! imagen_existe "lab-web-v1"; then
  construir_imagen web lab-node-v1 \
    "apache2 php libapache2-mod-php" \
    'a2enmod php8.4 >/dev/null 2>&1 || true; systemctl enable apache2'
fi

if ! imagen_existe "lab-ids-v1"; then
  construir_imagen ids lab-node-v1 "suricata"
fi

if ! imagen_existe "lab-attacker-v1"; then
  # nikto no está en los repositorios de Debian 13
  construir_imagen attacker lab-node-v1 \
    "masscan whatweb ffuf gobuster dirb tshark tcpflow"
fi

echo "== paquetes de los toolsets, para poder instalarlos sin Internet"
TOOLSETS="nmap masscan dnsutils whatweb whois curl ffuf gobuster dirb jq \
tcpdump tshark bettercap tcpflow hydra john medusa openssl sslscan \
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

echo "== consola limpia"
# El TTY de la caja es para el administrador, no para el log del kernel: cuando
# Incus crea bridges y dnsmasq, el kernel inunda la consola y no se lee nada.
cat > /etc/sysctl.d/90-consola.conf <<'SYSCTL'
# Solo emergencias y alertas en la consola; el resto va a dmesg.
kernel.printk = 3 4 1 7
SYSCTL
sysctl --system >/dev/null 2>&1 || true

# El prompt de login recuerda lo que no es evidente: cómo entrar y qué hacer.
if ! grep -q "netseclab box" /etc/issue 2>/dev/null; then
  echo "netseclab box - log in as lab / netseclab, then: lab --help" >> /etc/issue
fi

if [ -f /etc/default/grub ]; then
  if ! grep -q 'GRUB_CMDLINE_LINUX_DEFAULT=".*quiet' /etc/default/grub; then
    sed -i 's/^GRUB_CMDLINE_LINUX_DEFAULT="\(.*\)"/GRUB_CMDLINE_LINUX_DEFAULT="\1 quiet"/' \
      /etc/default/grub
    update-grub >/dev/null 2>&1 || true
  fi
fi

echo "== limpieza para distribuir"
# El artefacto no debe llevar laboratorios a medio montar: ni instancias ni redes
# `nvm-*`. Las imágenes y el perfil sí se quedan.
for instancia in $(incus list --format csv | cut -d, -f1); do
  [ -n "$instancia" ] && incus delete "$instancia" --force >/dev/null 2>&1 || true
done
for red in $(incus network list --format csv | cut -d, -f1 | grep '^nvm-' || true); do
  incus network delete "$red" >/dev/null 2>&1 || true
done
incus profile delete netseclab >/dev/null 2>&1 || true
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
