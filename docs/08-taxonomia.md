# Taxonomía y nomenclatura

> Vocabulario del proyecto. Si algo se llama de otra forma en el código, aquí se dice.

---

## 1. Las piezas

```
Caja  ·  la VM de VMware que se importa. Contiene Incus y las imágenes.
│
├── Imagen  ·  plantilla de nodo (lab-node-v1, lab-web-v1, …). Read-only.
│
└── Laboratorio  ·  lo que un profesor publica y un alumno ejecuta.
    │
    ├── Escenario  ·  la red concreta: segmentos, nodos y políticas.
    │   ├── Segmento  ·  cada red aislada (/24) con su bridge.
    │   └── Nodo      ·  cada máquina del escenario (contenedor de Incus).
    │
    ├── Ejercicios  ·  enunciado + comprobaciones sobre el escenario.
    │
    ├── Assets      ·  ficheros del escenario: webs, reglas, configuraciones.
    └── Tools       ·  binarios o paquetes que viajan con el laboratorio.
```

| Término | Qué es | En el código |
|---|---|---|
| **Caja** | La VM de VMware. El artefacto que se descarga e importa. | `images/box/` |
| **Imagen** | Plantilla de nodo. Una Debian con lo necesario dentro. | `lab/images.yaml`, `lab-node-v1` |
| **Laboratorio** | El paquete completo que se comparte: escenario + ejercicios + assets + tools. | `.labpack` |
| **Escenario** | La red concreta: segmentos, nodos y políticas de un caso. | `lab.yaml` |
| **Segmento** | Cada red aislada con su bridge (`ext`, `dmz`, `int`). | `networks:` |
| **Nodo** | Cada máquina del escenario. **No es una VM**: es un contenedor de sistema. | `nodes:` |
| **Ejercicio** | Enunciado con tareas y comprobaciones autocorregibles. | `exercises/*.yaml` |
| **Toolset** | Conjunto de herramientas con un propósito (`recon`, `webfuzz`). | `lab/toolsets.yaml` |
| **Assets** | Ficheros que se copian dentro de un nodo. | `assets:` |
| **Tools** | Herramientas que viajan con el laboratorio y se instalan en un nodo. | `tools:` (pendiente) |

### Por qué «nodo» y no «VM»

Porque no son máquinas virtuales: son contenedores de sistema que comparten el kernel de la caja.
Llamarlas VM promete algo que no son —un kernel propio, arranque, módulos— y genera expectativas
que no se cumplen. La caja **sí** es una VM; los nodos no.

Cuando haya nodos de Windows (**ver §4**), esos sí serán VMs, y el YAML lo dirá: `kind: vm`.

---

## 2. Tipos de laboratorio

No todos necesitan lo mismo, y sobre todo no todos pueden permitirse Internet.

| Tipo | Ejemplo | Internet | Aislamiento |
|---|---|---|---|
| **Red empresarial / blackbox** | Red team sobre una red con datos plantados por el profesor | **No** | Total |
| **Detección / SOC** | Suricata, logs, correlación, triaje | **No** | Total |
| **Herramientas** | Instalar, compilar o usar una utilidad nueva | Opcional | Parcial |
| **OSINT / reconocimiento pasivo** | whois, DNS, certificados, Shodan | **Sí** | Con salida |

El diseño por defecto (todo cerrado) es correcto para los dos primeros, que son la mayoría. Los
otros dos necesitan una salida a Internet **declarada**, no implícita.

---

## 3. Internet como capacidad, no como defecto

Mi postura inicial era «sin Internet por defecto», y sigo pensando que es el defecto correcto.
Pero como dogma es un error: hay laboratorios que sin Internet no existen.

La salida se declara por segmento, y es un tipo de red que ya está en el modelo:

```yaml
networks:
  ext:
    cidr: 10.20.0.0/24
    type: nat          # este segmento sí sale a Internet
```

Y se activa explícitamente al levantar:

```bash
lab up labs/osint/lab.yaml --uplink
```

### Por qué sigue siendo off por defecto

- **Reproducibilidad**: los resultados cambian según el día, el mirror y la red del aula. Un alumno
  obtiene una respuesta y otro otra.
- **Legal**: el tráfico de escaneo sale con la IP de la institución, no con la del alumno.
- **Aula**: treinta alumnos descargando o escaneando a la vez no es viable.
- **Seguridad**: una salida abierta es también una vía de exfiltración en un laboratorio cuyo
  objetivo es atacar máquinas.

### El problema de la reproducibilidad, y una idea

Para los laboratorios de OSINT, la salida a Internet se puede **grabar y reproducir**: el profesor
ejecuta el laboratorio una vez con Internet, un proxy registra las respuestas, y el laboratorio se
publica con esas grabaciones. El alumno las reproduce sin red y obtiene **exactamente** los mismos
resultados que el profesor.

Eso convierte un laboratorio no reproducible en uno reproducible, y el escenario sigue siendo
hermético. Queda como idea para cuando existan los laboratorios de OSINT; no está implementado.

---

## 4. Nodos de Windows

Posible, pero es otro nivel y conviene saber por qué antes de intentarlo.

**Lo que hace falta:**

1. **Virtualización anidada en VMware**: `vhv.enable = "TRUE"` en el `.vmx`, y una CPU que lo soporte
   (Intel VT-x/EPT o AMD SVM expuestos al invitado). Sin eso, no hay forma razonable.
2. **Incus con VMs**: `incus launch <imagen> <nodo> --vm` usa QEMU y necesita `/dev/kvm` dentro de
   la caja.
3. **Una imagen de Windows**: hay que construirla desde un ISO con `distrobuilder`. Son ~10 GB por
   imagen y **licencia de Windows**.

**Los problemas de verdad:**

- **Licencia**: distribuir una imagen de Windows en un paquete de laboratorio no es defendible. Los
  ISOs de evaluación de Microsoft caducan y tienen condiciones de uso.
- **Tamaño**: una imagen de Windows pesa más que toda la caja actual.
- **Rendimiento**: anidar KVM sobre KVM sobre Hyper-V/VMware es lento y frágil; es justo el infierno
  que este proyecto quiso evitar.

**Atajo que cubre buena parte del temario**: un **Samba AD DC** en un nodo Linux emula un dominio
Active Directory lo suficiente para Kerberoasting, AS-REP roasting, enumeración de usuarios y
políticas, y ataque a credenciales. No es idéntico, pero enseña los mismos conceptos sin licencias ni
10 GB.

**Posición**: los nodos Windows son un objetivo de segunda fase, y solo para quien acepte el coste
de la licencia. La arquitectura lo permite (`kind: vm` en el YAML); el PoC no los necesita.
