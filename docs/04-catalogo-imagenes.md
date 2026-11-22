# Catálogo de imágenes, toolsets y SOC

> La plataforma va de un laboratorio de *fuzzing* de tres nodos a un SOC con SIEM. No se consigue con
> una imagen por escenario, sino con **pocas imágenes base + piezas componibles**.

---

## 1. Las tres capas de composición

```
imagen base  +  toolsets  +  startup  +  assets  =  nodo del laboratorio
(Debian 13)     (recon)     (script)    (webapp)
```

| Capa | Qué aporta | Coste |
|---|---|---|
| **Imagen** | SO base con lo imprescindible (`debian13`, `web`, `ids`, `soc-lite`) | Se construye una vez, se cachea |
| **Toolset** | Conjunto pequeño de herramientas con un propósito (`recon`, `webfuzz`, `sniff`) | Paquetes, en caché local |
| **`startup` + `assets`** | Configuración y ficheros del escenario (reglas nft, reglas Suricata, la web vulnerable, el wordlist) | Depende del ejercicio |

La razón de hacerlo así: el mismo `debian13` sirve para una víctima, un atacante y un router. Lo que
cambia es lo que lleva encima.

---

## 2. Toolsets

Se declaran en un fichero del repositorio y se aplican por nodo o por perfil.

```yaml
# lab/toolsets.yaml
recon:
  packages: [nmap, masscan, dnsutils, whatweb, whois]
  size: ~25 MB

webfuzz:
  packages: [ffuf, gobuster, nikto, dirb, curl, jq]
  assets: [wordlists/common-2k.txt]     # wordlist curada, ~40 KB
  size: ~30 MB

sniff:
  packages: [tcpdump, tshark, bettercap, mitmproxy, tcpflow]
  size: ~120 MB

crack:
  packages: [hydra, john, hashcat, medusa]
  size: ~60 MB

tls:
  packages: [openssl, sslscan, testssl.sh, certbot]
  size: ~15 MB

blue:
  packages: [auditd, aide, fail2ban, rkhunter, lynis]
  size: ~40 MB

traffic:
  packages: [hping3, scapy, iperf3, tcpreplay, dsniff]
  size: ~30 MB
```

Se instalan en la creación del nodo desde la **caché local** de la caja, así que funciona sin
Internet. `lab toolsets` lista los disponibles y su tamaño; `lab image build` los preinstala si se
quiere una imagen ya cargada.

> Nada de Kali: 3–4 GB, 600 herramientas y cero criterio. Cada ejercicio declara el set mínimo, y el
> alumno aprende a elegir la herramienta porque solo tiene esa.

---

## 3. Catálogo de imágenes

| Imagen | Contenido | RAM en reposo | Para qué |
|---|---|---|---|
| `debian13` | SO mínimo, `ssh`, `iproute2`, `nftables` | ~40 MB | Víctimas, routers, nodos neutros |
| `web` | `apache2` + `php` + `mariadb` + web de ejemplo | ~120 MB | Servidores web del escenario |
| `attacker` | `debian13` + toolsets `recon` + `webfuzz` + `sniff` | ~70 MB | Máquina atacante |
| `ids` | `suricata` + reglas propias + `eve.json` | ~150 MB | Sensor de red |
| `soc-lite` | `grafana` + `loki` + `vector` + dashboards | ~400 MB | SOC ligero, el que cabe en un portátil |
| `soc-wazuh` | Wazuh all-in-one (manager + indexer + dashboard) | ~4 GB | SOC completo, solo en equipos grandes |
| `monitoring` | `prometheus` + `grafana` + `node_exporter` | ~250 MB | Monitorización de infraestructura |
| `fileserver` | `vsftpd` + `samba` + `nginx` | ~90 MB | Víctima de servicios de ficheros |

Estas son las de fábrica. Cualquiera puede crear las suyas (§5).

---

## 4. SOC: simulado y real

Se piden las dos cosas y ninguna de las dos es cara si se elige bien.

```yaml
telemetry:
  soc: soc                    # nodo que recibe y correlaciona
  sources: [auth, syslog, suricata]
  retention: 24h
```

`lab` configura **`rsyslog`** en cada nodo (ya está en Debian, sin repositorios de terceros) para
reenviar su syslog y, si el ejercicio lo pide, seguir ficheros JSON como el `eve.json` de Suricata.
El nodo SOC escucha por TCP en el 514 y escribe un fichero por nodo y día en `/var/log/lab/<nodo>/`.
Con eso:

- **Real**: Suricata en el `fw` genera alertas de verdad; el SOC las recibe y las almacena. Las
  comprobaciones `ids-alerts` se hacen contra el log real del IDS.
- **Simulado**: un nodo `generator` produce eventos con `syslog` de ataque (fuerza bruta SSH,
  escaneos) sin montar la red entera. Sirve para enseñar a usar el SIEM sin gastar recursos.

Sobre la visualización: el colector deja los datos en ficheros, así que se pueden consultar con
`grep`/`jq` desde el propio ejercicio. Añadir Grafana o Wazuh encima es un paso posterior y opcional,
con el coste de RAM que indica la tabla de abajo.

### Elección de SIEM

| Opción | RAM | Aporte didáctico | Veredicto |
|---|---|---|---|
| **Grafana + Loki + Vector** (`soc-lite`) | ~400 MB | Ingesta, consultas, dashboards, alertas | **Por defecto** |
| **Wazuh** (`soc-wazuh`) | ~4 GB | SIEM completo: reglas, correlación, casos, agentes | Opcional, en equipo con 8 GB+ |
| ELK / OpenSearch | 2–4 GB | Potente, mucho que mantener | No |
| Security Onion | 8–16 GB | Excelente y enorme | No |

`soc-lite` no es un SIEM de juguete: es el mismo patrón (agente → colector → almacén → panel →
alerta). Lo que no tiene es motor de correlación de reglas, y eso es justo lo que se aprende con
Wazuh. Por eso el catálogo ofrece los dos y el laboratorio avisa del coste.

---

## 5. Imágenes propias

Una receta es un YAML pequeño:

```yaml
# images/recipes/soc-lite.yaml
name: soc-lite
base: images:debian/13
description: Grafana + Loki + Vector con dashboards de Suricata y auth
packages: [grafana, loki, promtail, vector, jq]
assets:
  - { src: assets/grafana/dashboards, dst: /var/lib/grafana/dashboards }
  - { src: assets/loki/loki.yaml,      dst: /etc/loki/config.yaml }
startup: |
  systemctl enable --now loki grafana-server vector
size: 8GB
```

```bash
lab image build soc-lite          # construye, valida y publica como lab/soc-lite:1
lab image ls                      # catálogo local con tamaño y fecha
lab image rm soc-lite:1
```

Construir la imagen es útil cuando el proceso de instalación es largo (un SIEM) o cuando varios
ejercicios la comparten. Para todo lo demás, `packages:` y `startup:` en el nodo bastan y son más
rápidos de iterar.

---

## 6. Aserciones nuevas: detectar, no detectar, y haber llegado

Los ejercicios de SOC y de evasión necesitan comprobar cosas que no son "responde un ping".

```yaml
checks:
  # el ataque llegó
  - assert: http-status  evil1 -> http://www.lab/admin/  is 200
  - assert: file         www  /var/www/html/.git/config exists

  # el IDS no lo vio
  - assert: ids-alerts   since: last, src: evil1, count: 0
  # o lo vio, y toca explicarlo
  - assert: ids-alerts   since: last, src: evil1, sig: "ET WEB_SERVER" count: ">= 1"

  # el cortafuegos no bloqueó (o sí)
  - assert: fw-counters  fw  chain: forward, verdict: accept, delta: "> 0"

  # la captura contiene la petición
  - assert: capture      dmz, since: last, contains: "GET /admin/"
```

| Tipo | Comprueba |
|---|---|
| `reachable`, `port-state`, `http-status`, `file` | Resultado del ataque |
| `ids-alerts` | Alertas del IDS/SIEM (por origen, firma, ventana de tiempo) |
| `fw-counters` | Contadores de nftables/iptables |
| `capture` | Contenido del pcap del segmento |
| `answer` | Preguntas de razonamiento |

Con esto, un ejercicio como "haz fuzzing sin que te detecten" **se corrige solo**: o hay cero alertas
con tu IP de origen, o no hay nota. Y al revés, un ejercicio de defensa puede exigir que el IDS
disponga de una firma concreta y que el atacante no pase.

---

## 7. Presupuesto según lo que se monte

| Laboratorio | Nodos | RAM | Disco |
|---|---|---|---|
| Fuzzing + evasión (`fw`, `www`, `evil1`) | 3 | ~600 MB | ~3 GB |
| Pentesting completo (recon, pivote, DMZ, interna) | 8 | ~1,2 GB | ~4 GB |
| SOC real con `soc-lite` + IDS + víctima | 5 | ~1,1 GB | ~4 GB |
| SOC completo con `soc-wazuh` | 5 | ~4,8 GB | ~8 GB |

La caja se dimensiona con 2 vCPU y 2 GB para los tres primeros y 4 vCPU / 8 GB para Wazuh. Es la
única decisión que cambia con el escenario, y el laboratorio debe avisar antes de arrancar.
