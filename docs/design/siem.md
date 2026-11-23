# SIEM ligero para el laboratorio

Esta página diseña el SIEM que usan las prácticas de detección y respuesta. No es un SOC de
producción: es una herramienta docente que cabe en un nodo del laboratorio, se corrige sola y enseña
lo que importa —reglas, correlación, triaje—, no a manejar un panel.

## El problema

Un laboratorio de blue team necesita un SIEM. Las opciones conocidas no caben:

| Opción | Por qué no |
|---|---|
| Wazuh | Agente + gestor + índice + panel: cientos de MB y servicios que arrancan solos. |
| Elastic/ELK | JVM, varios procesos, GB de RAM. |
| Loki + Grafana | Menos pesado, pero son dos servidores más y una UI web que aquí no aporta. |

La caja tiene 2 GB de RAM y el nodo del SOC no puede llevarse medio laboratorio. Además, el objetivo
didáctico es **escribir y entender reglas y casos de uso**, no aprender a instalar un producto.

## Principios

1. **Terminal, sin dependencias nuevas.** Python con biblioteca estándar (`sqlite3` incluido) y el
   `PyYAML` que el proyecto ya usa. Ni JVM, ni Node, ni motor de búsqueda.
2. **Replay primero.** Las prácticas se corrigen con conjuntos de eventos preparados, no con el
   tráfico que el alumno haya generado ese día. Si un caso de uso no se puede reproducir, no se puede
   corregir.
3. **El SIEM es el motor de reglas.** La interfaz es `siem query` y `siem alerts`. Un panel web puede
   llegar después; no es el producto.
4. **Un proceso, un fichero.** Todo el estado vive en un SQLite del nodo SOC.

## Arquitectura

```
 fuentes                ingesta             normalización        almacén         correlación        salida
──────────────────────────────────────────────────────────────────────────────────────────────────────────
 auth.log   ─┐
 syslog     ─┼─► siem ingest/listen ─► parsers ──────────► SQLite ──────► reglas YAML ──► alertas
 eve.json   ─┘   (stdin, 514, tail)     (eve, sshd,          (events,      (match, grupo,    (tabla +
                                        dnsmasq, jsonl)      alerts)       ventana, umbral,  fichero)
                                                                           secuencia)
                                                                                 │
                                                                                 ▼
                                                                          siem query / alerts
```

| Pieza | Decisión | Por qué |
|---|---|---|
| Ingesta | `siem ingest` (fichero o stdin), `siem listen` (UDP/TCP 514) y `siem follow` (tail) | rsyslog ya centraliza los logs en el nodo SOC; el modo fichero sirve para los casos preparados |
| Normalización | Esquema mínimo común; lo que no se reconoce entra como `raw` | Un log desconocido no se pierde y se puede enseñar a parsearlo |
| Almacén | SQLite en modo WAL, una tabla `events` y otra `alerts` | Biblioteca estándar, consultas SQL, sin servidor |
| Correlación | Reglas en YAML evaluadas **por lotes con SQL** | Para enseñar, una regla que se lee es mejor que una máquina de estados opaca |
| Alertas | Tabla + fichero, con supresión por `(regla, clave)` | Sin duplicados ni inundación: lo que se corrige es la alerta, no el ruido |
| Retención | Borrar por antigüedad (`retention`) | El nodo SOC no crece sin control |

### Esquema de eventos

| Campo | Ejemplo | Notas |
|---|---|---|
| `ts` | epoch con milisegundos | Índice principal |
| `host` | `fw`, `dmza` | Quién lo emitió |
| `source` | `suricata`, `sshd`, `dnsmasq` | Parser que lo interpretó |
| `kind` | `alert`, `login-failed`, `dns-query` | Lo que usa el alumno en las reglas |
| `src_ip`, `dst_ip`, `src_port`, `dst_port` | `10.30.0.10`, `10.30.1.10`, `51234`, `80` | Lo que se correlaciona |
| `user`, `action`, `severity` | `user1`, `scan`, `high` | Campos de la práctica |
| `message` | `ET SCAN nmap` | Texto corto y buscable |
| `fields` | JSON con el resto | Sin perder detalle |
| `raw` | línea original | Para investigar |

## Reglas: el lenguaje que aprende el alumno

```yaml
rules:
  - id: ssh-bruteforce
    title: Fuerza bruta contra SSH
    severity: high
    match: { kind: login-failed }
    group_by: [src_ip]
    window: 5m
    threshold: { count: 5 }
    suppress: 10m

  - id: port-scan
    title: Escaneo de puertos
    severity: medium
    match: { source: suricata, kind: alert, message: "*SCAN*" }
    group_by: [src_ip]
    window: 2m
    threshold: { count: 3 }

  - id: scan-then-exploit
    title: Escaneo seguido de intento de explotación
    severity: critical
    sequence:
      - { match: { source: suricata, message: "*SCAN*" }, group_by: [src_ip], within: 10m }
      - { match: { source: suricata, severity: high }, group_by: [src_ip], within: 5m }
```

Las tres formas —evento, umbral y secuencia— cubren la mayoría de casos de uso de un curso: fuerza
bruta, escaneo, exfiltración por volumen, acceso después de fallos y «esto pasó justo después de
aquello». `siem rules test` valida el YAML antes de arrancar; un error dice la regla y el campo.

## Reproducibilidad: casos y pruebas doradas

Un **caso** es una carpeta con eventos y lo que se espera de ellos:

```
casos/ssh-bruteforce/
├── eventos/          auth.log, eve.jsonl, syslog
├── reglas.yaml
└── esperado.yaml     alertas que tienen que salir (regla, severidad, src_ip, count)
```

`siem replay casos/ssh-bruteforce` ingesta los eventos y compara las alertas con las esperadas. Eso
da dos cosas: el ejercicio se corrige igual lo haya generado el alumno o no, y **las reglas se prueban
en el CI**, como el código.

## Integración con el laboratorio

- **Nodo `soc`**: imagen propia (receta) con `rsyslog` y el SIEM. La telemetría del laboratorio ya
  manda `auth`, `syslog` y `suricata` a ese nodo; no hay que inventar transporte.
- **Comprobación nueva**: `siem-alerts rule=ssh-bruteforce count=1` (o `count>=1`), con el mismo
  espíritu que `ids-alerts` pero contra la tabla de alertas del SIEM. Es lo que permite autocorregir
  un ejercicio de triaje.
- **Ejercicio de analista**: un atacante guionizado en `assets` genera el incidente; el alumno busca
  en `siem query`, identifica el origen, aplica la respuesta (bloquear en `fw`) y escribe el informe.
  Las comprobaciones verifican la alerta, el bloqueo (`reachable ... is false`) y las respuestas.

## Empaquetado y mantenimiento

**Ahora**: paquete independiente dentro del repositorio, `src/siem/`, con las mismas reglas que
`tynix`: no importa nada de `lab`, se prueba por su cuenta y solo usa biblioteca estándar más
`PyYAML`. Coste de mantenimiento: cero extra, porque comparte CI, estilo y versionado.

**Repo aparte** cuando se cumpla algo de esto, y se decide entonces, no antes:

1. el CLI del laboratorio solo lo invoca como comando, sin importar su API;
2. crecen las reglas o los casos hasta ser un proyecto en sí (unas 3.000 líneas o reglas de terceros);
3. necesita su propia cadencia de versiones;
4. lo usan fuera del laboratorio.

Si se separa: `netseclab-siem` con su paquete en PyPI, y la caja lo instala en la receta del nodo
SOC. El laboratorio solo necesita el ejecutable `siem`.

**Las reglas no van en el código.** Van en un directorio de YAML versionado aparte para que un
profesor añada un caso de uso sin tocar el motor ni esperar una release.

## Consumo estimado

| Recurso | Estimación |
|---|---|
| RAM del proceso | 30–50 MB |
| CPU | 1 vCPU, a ráfagas |
| Disco | eventos de ~1 KB; 48 h de laboratorio, decenas de MB |

Cabe en un nodo con 512 MB, que es lo que necesita el SOC para `rsyslog` y el motor juntos.

## Lo que no se va a hacer

Panel web, alta disponibilidad, ingesta distribuida, retención de meses, parseo universal de formatos
o sustituir a un SIEM de producción. Si algún día hace falta, el SIEM exporta sus alertas y otro
sistema las recoge.

## Plan de implementación

1. **Núcleo**: esquema, parsers (`eve`, `sshd`, `dnsmasq`, `jsonl`), `ingest`, `query` y pruebas con
   ficheros de ejemplo.
2. **Motor de reglas**: `match`, `group_by`, `window`, `threshold`, `suppress`, `sequence` y
   `rules test`.
3. **Replay**: casos con eventos y alertas esperadas, ejecutados en el CI.
4. **Integración**: receta del nodo `soc`, comprobación `siem-alerts` y telemetría.
5. **Contenido**: laboratorio `soc-lab` y ejercicio de triaje con informe.

Cada paso deja algo usable; ninguno obliga a rehacer el anterior.
