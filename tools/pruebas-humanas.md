# Pruebas humanas de la caja

Lo que el CI y `tools/probar-caja.sh` no pueden comprobar: que dentro de VMware, con la interfaz de
verdad, el laboratorio se comporta como dice la documentación y los ejercicios se entienden.

Se hace **una vez por versión publicada**, con el artefacto que se va a entregar.

## Preparación

```bash
sha256sum -c SHA256SUMS
tar -xzf netseclab-*-vmware.tar.gz
# abrir netseclab.vmx con VMware Workstation o Player
```

| Dónde | Usuario | Contraseña |
|---|---|---|
| La caja (consola de VMware) | `lab` | `netseclab` |
| Los nodos del laboratorio | `root` | `netseclab` |
| Los nodos del laboratorio | `user1` | `netseclab` |

En el primer arranque: `passwd` y `lab --version` (tiene que decir la versión del artefacto).

## 1. El laboratorio de ejemplo

```bash
lab up /opt/netseclab/lab/examples/example.net.yaml --profile full
lab status
```

- [ ] Cien pasos, sin errores, y `snapshot 'initial' created`.
- [ ] Siete nodos en `Running`.
- [ ] `free -m` deja margen; `df -h /` no pasa del 60 %.
- [ ] `lab up` otra vez no rompe nada (es idempotente).
- [ ] `lab down ... --profile full` y después `lab up` lo vuelven a dejar todo en marcha.
- [ ] `lab reset` vuelve al snapshot `initial`.

## 2. La diferencia entre closed y filtered

Desde `exta`:

```bash
incus exec exta -- ip route          # tiene que haber rutas por 10.5.0.254
incus exec exta -- nmap -Pn -p22,80,443 www.example.net
```

- [ ] 80 `open`, 443 `closed`, 22 `filtered`.
- [ ] `lab console exta` abre consola; se sale con `Ctrl-a` y `q`.

## 3. Los seis ejercicios, con criterio docente

Para cada uno: leer enunciado, tareas, pistas, comprobaciones y solución; ejecutar `lab check` y
comprobar que los hechos del entorno pasan y que la solución escrita obtiene la puntuación completa.

- [ ] `01-reconocimiento` — ¿las pistas ayudan sin resolver? ¿la solución da 5/5?
- [ ] `02-conectividad` — ¿se ve el efecto de las rutas del segmento y del DNS?
- [ ] `03-captura` — ¿el pcap se genera en el modo declarado?
- [ ] `04-pivoteo` — ¿el pivoteo usa el cortafuegos de verdad?
- [ ] `05-endurecimiento` — **ojo**: exige encontrar el cortafuegos del servidor.
- [ ] `06-fuzz-evasion` — **ojo**: depende del umbral real de Suricata y del tiempo de captura.

```bash
lab check /opt/netseclab/lab/exercises/01-reconocimiento.yaml
lab answer /opt/netseclab/lab/exercises/01-reconocimiento.yaml puerto-cerrado 443
lab report /opt/netseclab/lab/exercises/01-reconocimiento.yaml --out informe.md
```

Un alumno real tarda unos 20 minutos por ejercicio; la prueba es que el enunciado se entienda sin
explicaciones y que el informe salga legible.

## 4. Paquetes firmados

```bash
cd /opt/netseclab
ssh-keygen -q -t ed25519 -N "" -f /tmp/prof -C profesor@universidad
lab pack lab/examples/example.net.yaml --out /tmp/e.labpack --sign /tmp/prof
lab unpack /tmp/e.labpack --to /tmp/extraido --signer /tmp/prof.pub
```

- [ ] `pack` dice `packed …` y `signed: …labpack.sig`.
- [ ] `unpack` dice `signature ok: Good "netseclab" signature … SHA256:…`.
- [ ] Con `--signer /tmp/otro.pub` falla con exit 2 y no extrae nada.
- [ ] Sin `--signer`, el mismo paquete se extrae (checksums de siempre).

Descarga por URL con un servidor de verdad:

```bash
cd /tmp && python3 -m http.server 8000 &
lab unpack http://127.0.0.1:8000/e.labpack --to /tmp/desde-url \
  --signer http://127.0.0.1:8000/prof.pub
```

- [ ] Verifica la firma y extrae, sin rutas temporales raras en la salida.

## 5. Caché de imágenes

```bash
mkdir -p /tmp/bucket
lab push lab-node-v1 --to /tmp/bucket
lab pull lab-node-v1 --from /tmp/bucket --as node-base
lab gc /opt/netseclab/lab/examples/example.net.yaml
```

- [ ] `push` escribe el `.tar.gz` y `index.json`; `pull` dice `sha256 verified`.
- [ ] `gc` sin `--yes` solo enseña lo que borraría; no toca `lab-node-v1` ni `lab-web-v1`.

## 6. Consolas en el navegador

```bash
lab web --port 8080 --token prueba
# desde VMware: http://127.0.0.1:8080/?token=prueba
```

- [ ] Cada nodo abre su consola y responde a las teclas.
- [ ] Sin el token (`http://127.0.0.1:8080/`) devuelve **401** y no filtra el token.

## 7. Lo que se apunta

- [ ] Tamaño del artefacto y del VMDK descomprimido.
- [ ] Cualquier paso que tarde demasiado o falle a la primera.
- [ ] Diferencias entre la documentación y lo que pasa en la VM.

Lo que salga de aquí decide si se etiqueta la versión o se arregla algo antes.
