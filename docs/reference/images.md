# Imágenes y toolsets

Esta página describe las imágenes de nodo del catálogo, los conjuntos de herramientas y las recetas
para construir imágenes propias.

## Tres capas de composición

Un nodo se compone de una imagen base, un conjunto de herramientas y la configuración del escenario:

```
imagen base  +  toolsets  +  packages  +  startup  +  assets  =  nodo del laboratorio
(debian13)      (recon)                    (script)    (webapp)
```

| Capa | Qué aporta | Cuándo se usa |
|---|---|---|
| **Imagen** | Sistema base con lo imprescindible. | Se construye una vez y se reutiliza. |
| **Toolset** | Paquetes con un propósito. | Se declara por nodo con `toolsets:`. |
| **`packages` + `startup` + `assets`** | Configuración y ficheros del escenario. | Se aplican al levantar el laboratorio. |

La misma Debian sirve para una víctima, un atacante y un router; lo que cambia es lo que lleva encima.
El catálogo usa conjuntos pequeños para que el alumno tenga que elegir la herramienta.

## Catálogo de imágenes

`lab/images.yaml` traduce alias del catálogo a referencias de Incus:

```bash
lab images
```

| Alias | Referencia | Contenido | Construida por |
|---|---|---|---|
| `debian13` | `lab-node-v1` | Debian 13 con `openssh-server`, `iproute2`, `nftables`, `curl`, `jq`, `tcpdump`, `nmap`, `rsyslog`, `isc-dhcp-client` y `dnsmasq`. | La caja |
| `web` | `lab-web-v1` | `lab-node-v1` con `apache2`, `php` y `libapache2-mod-php`. | La caja |
| `ids` | `lab-ids-v1` | `lab-node-v1` con `suricata`. | La caja |
| `attacker` | `lab-attacker-v1` | `lab-node-v1` con `masscan`, `whatweb`, `ffuf`, `gobuster`, `dirb`, `tshark` y `tcpflow`. | La caja |
| `soc-lite` | `lab-soc-lite-v1` | Apunta a una imagen de SOC que **no** se construye en el repositorio. | Sin receta |

Las cuatro primeras las construye `images/box/provision.sh` durante la construcción de la caja y
quedan cacheadas: el laboratorio funciona sin Internet. `soc-lite` es un alias reservado:
`lab/images.yaml` apunta a `lab-soc-lite-v1`, pero no hay receta en `images/recipes/` ni imagen
construida. Para usar el alias hay que publicar una imagen con esa referencia o cambiar el catálogo.

Las imágenes de nodo (`debian13` y las que derivan de ella) incluyen `root` y `user1`, ambos con la
contraseña `netseclab`, y el SSH acepta contraseña. El prompt recuerda cómo salir de la consola
(`Ctrl-a`, luego `q`).

## Toolsets

Los toolsets viven en `lab/toolsets.yaml` y se aplican por nodo:

```yaml
nodes:
  - name: evil1
    image: attacker
    toolsets: [recon, webfuzz]
```

| Toolset | Paquetes |
|---|---|
| `recon` | `nmap`, `masscan`, `dnsutils`, `whatweb`, `whois`, `curl` |
| `webfuzz` | `ffuf`, `gobuster`, `dirb`, `curl`, `jq` |
| `sniff` | `tcpdump`, `tshark`, `bettercap`, `tcpflow` |
| `crack` | `hydra`, `john`, `medusa` |
| `tls` | `openssl`, `sslscan`, `certbot` |
| `blue` | `auditd`, `aide`, `fail2ban`, `lynis`, `rkhunter` |
| `traffic` | `hping3`, `scapy`, `iperf3`, `tcpreplay`, `dsniff` |
| `webapp` | `sqlmap`, `wfuzz`, `whatweb`, `curl` |

```bash
lab toolsets
```

Al levantar el laboratorio, el motor comprueba qué paquetes faltan y los instala con `apt` desde la
caché de `.deb` y los repositorios de la caja. Un toolset que no existe en `lab/toolsets.yaml` es un
error, no se ignora. Cada toolset del catálogo tiene entre tres y seis paquetes.

## Imágenes propias

Una receta es un YAML pequeño. Las del repositorio son:

```yaml
# images/recipes/web.yaml
name: web
base: debian13
version: "1"
description: Servidor web PHP con una página de ejemplo
size: 4GB
packages: [apache2, php, libapache2-mod-php, curl]
assets:
  - { src: assets/web, dst: /var/www/html }
startup: |
  a2enmod php8.4 >/dev/null 2>&1 || true
  systemctl enable --now apache2
```

| Clave | Obligatoria | Qué es |
|---|---|---|
| `name` | sí | Nombre de la imagen; se publica como `lab/<name>:<versión>`. |
| `base` | no | Alias del catálogo o referencia completa; por defecto `debian13`. |
| `version` | no | Versión de la imagen; por defecto `1`. |
| `description` | no | Texto libre. |
| `packages` | no | Paquetes que se instalan durante la construcción. |
| `assets` | no | Ficheros o directorios que se copian; cada uno con `src` y `dst`. |
| `startup` | no | Script que se ejecuta al final de la construcción. |
| `size` | no | Tamaño del disco raíz de la instancia de construcción. |

```bash
lab image build images/recipes/web.yaml
lab image build images/recipes/attacker.yaml --dry-run
```

```
image lab/web:1 from debian13 (9 steps)
-> incus delete lab-build-web --force
-> incus launch lab-node-v1 lab-build-web --profile netseclab
-> incus config device override lab-build-web root size=4GB
...
```

Al terminar una construcción real, `lab` imprime el resumen de pasos y recuerda que
`lab image ls` debe mostrar la imagen.

La construcción es una instancia temporal de un solo uso:

1. Borra los restos de un intento anterior.
2. Arranca una instancia desde la imagen base.
3. Ajusta el disco si la receta declara `size`.
4. Instala los paquetes.
5. Copia los `assets`; los directorios se envían con `tar` y los ficheros como texto.
6. Ejecuta el `startup`.
7. Para la instancia, la publica con el alias `lab/<name>:<versión>` y la borra.

El alias que publica una receta (`lab/web:1`, por ejemplo) no entra en `lab/images.yaml`. Para usarla
desde una topología hay que referenciar la referencia completa (contiene `:` o `/`) o añadir el alias
al catálogo.

Construir una imagen tiene sentido cuando la instalación es larga o la comparten varios ejercicios.
Para todo lo demás, `packages:` y `startup:` en el nodo son más rápidos de iterar. La construcción
necesita Incus y acceso a los repositorios de Debian; la caja sale por la NAT de VMware.

```bash
lab image ls        # imágenes locales con alias lab/
lab image rm lab/web:1
```

## Recursos

Los nodos usan por defecto 1 vCPU y 256 MB de RAM; se cambian con `resources:` en la topología. Las
imágenes con servicios pesados necesitan más.

La caja se dimensionó con 2 vCPU y 2 GB de RAM. Las medidas durante la validación fueron: artefacto
de ~1,9 GB, ~4,2 GB de disco con siete nodos y snapshots, y ~1,3 GB de RAM libres con todo levantado.
El disco de la caja es de 12 GB virtuales. Un escenario con más nodos o con un SIEM completo necesita
más RAM de la que ofrece ese dimensionado.

## Relación con tynix

Un nodo también puede declarar un `environment:` en vez de una imagen: base y paquetes se resuelven a
una imagen direccionada por contenido (`lab-env-*`), que se construye sola si no existe. Es la vía
recomendada para entornos reproducibles y para compartirlos con `lab push` y `lab pull`. Ver
[Compartir laboratorios](../guides/sharing.md).

## Pendiente

Las imágenes de SOC completas (Wazuh, Loki, Grafana) no están en el repositorio; solo existe el alias
`soc-lite`. Las imágenes de Windows no están contempladas. La verificación de las imágenes
distribuidas se apoya en `sha256`; el paquete `.labpack` que las acompaña sí se puede firmar con
`lab pack --sign`. Ver [Compartir laboratorios](../guides/sharing.md).
