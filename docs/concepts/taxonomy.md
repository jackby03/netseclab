# Taxonomía

Esta página fija el vocabulario del proyecto: qué es cada pieza y cómo se llama en la documentación,
en el YAML y en el código.

## Las piezas

```
Caja  ·  la VM de VMware que se importa. Contiene Incus y las imágenes.
│
├── Imagen  ·  plantilla de nodo (lab-node-v1, lab-web-v1, …). Solo lectura.
│
└── Laboratorio  ·  lo que un profesor publica y un alumno ejecuta.
    │
    ├── Escenario  ·  la red concreta: segmentos, nodos y políticas.
    │   ├── Segmento  ·  cada red con su bridge.
    │   └── Nodo      ·  cada máquina del escenario (contenedor de Incus).
    │
    ├── Ejercicios  ·  enunciado y comprobaciones sobre el escenario.
    ├── Assets      ·  ficheros del escenario: webs, reglas, configuraciones.
    └── Tools       ·  binarios o paquetes que viajan con el laboratorio (pendiente).
```

| Término | Qué es | En el código |
|---|---|---|
| **Caja** | La VM de VMware: el artefacto que se descarga e importa. | `images/box/` |
| **Imagen** | Plantilla de nodo con lo necesario dentro. | `lab/images.yaml`, `lab-node-v1` |
| **Laboratorio** | El conjunto que se comparte: escenario, ejercicios, assets y tools. | `.labpack` |
| **Escenario** | La red concreta de un caso: segmentos, nodos y políticas. | fichero de topología (`lab.yaml`) |
| **Segmento** | Cada red con su bridge (`ext`, `dmz`, `int`). | `networks:` |
| **Nodo** | Cada máquina del escenario; es un contenedor de sistema. | `nodes:` |
| **Ejercicio** | Enunciado con tareas, comprobaciones y respuestas. | `exercises/*.yaml` |
| **Toolset** | Conjunto de herramientas con un propósito (`recon`, `webfuzz`). | `lab/toolsets.yaml` |
| **Assets** | Ficheros que se copian dentro de un nodo. | `assets:` |
| **Tools** | Herramientas que viajan con el laboratorio (pendiente). | `tools:` |

En la documentación se usa **escenario** para el contenido del fichero YAML. El código lo llama
**topología** porque es la descripción de una red; ambos términos se refieren a lo mismo.

## Por qué «nodo» y no «VM»

Los nodos no son máquinas virtuales: son contenedores de sistema que comparten el kernel de la caja.
Llamarlos VM prometería un kernel propio, arranque y módulos que no tienen. La caja sí es una VM; los
nodos no.

Cuando existan nodos de Windows serán VMs de verdad. El formato no los contempla todavía.

## Escenario, segmento y laboratorio

Un **escenario** es una red concreta: los segmentos, los nodos que viven en ellos y las políticas del
cortafuegos. Se escribe en YAML y se valida antes de arrancar.

Un **segmento** es cada red aislada. Se declara con un `cidr`, un `type` (`isolated`, `nat`,
`bridged`) y un `mode` (`switch`, `hub`, `mirror`) que decide cómo se comporta el conmutador y, por
tanto, qué puede observar el alumno.

Un **laboratorio** es lo que se comparte: el escenario, uno o varios ejercicios, los assets y, si
hacen falta, herramientas propias. Se empaqueta en un `.labpack` cuando el contenido es solo texto y
ficheros.

## Ejercicio

Un ejercicio referencia un escenario y declara dos tipos de evaluación: **hechos** que la máquina
comprueba ejecutando comandos y **respuestas** que el alumno entrega como un valor concreto. Las
preguntas de razonamiento van en el informe escrito, que corrige el profesor. La corrección de un
ejercicio no depende de que alguien revise capturas de pantalla.

## Toolset y assets

Un **toolset** es una lista corta de paquetes de Debian con un propósito: `recon` para
reconocimiento, `webfuzz` para descubrimiento web. Se declara en `lab/toolsets.yaml` y se aplica por
nodo con `toolsets:`.

Los **assets** son ficheros del escenario que se copian dentro de un nodo: la web vulnerable, las
reglas de Suricata, un fichero de configuración. Se declaran con `assets:` y viajan con el
laboratorio.

## Herramientas por nodo

`tools:` está previsto para llevar un binario estático o un `.deb` dentro del laboratorio y copiarlo
al nodo durante `lab up`. No está implementado: hoy las herramientas se consiguen con una imagen
propia, con un toolset o con `packages:`.

## Tipos de laboratorio

| Tipo | Ejemplo | Internet | Aislamiento |
|---|---|---|---|
| Red empresarial o *blackbox* | Red team sobre una red con datos plantados | No | Total |
| Detección y SOC | Suricata, logs, correlación, triaje | No | Total |
| Herramientas | Instalar, compilar o usar una utilidad | Opcional | Parcial |
| OSINT o reconocimiento pasivo | whois, DNS, certificados, Shodan | Sí | Con salida |

## Internet como capacidad declarada

El diseño parte de que un escenario no sale a Internet salvo que lo declare. Un segmento `type: nat`
tiene NAT de salida a la caja y resuelve nombres por la puerta del bridge; el resto de segmentos, y
todo escenario sin uno `nat`, está aislado. Lo que **no** está implementado es el atajo
`lab up --uplink` (declarar la salida sin añadir el segmento a mano) ni la grabación y reproducción
del tráfico de Internet.

La documentación de referencia de [topología](../reference/topology.md) describe los tipos de red que
el modelo acepta.

## Nodos Windows

Los nodos Windows **no están implementados**. Incus puede lanzar VMs, pero dentro de la caja exigirían
virtualización anidada, una imagen de unos 10 GB y una licencia de Windows.

La alternativa prevista para cubrir Active Directory es un controlador de dominio **Samba AD** en un
nodo Linux: cubre Kerberoasting, AS-REP roasting, enumeración de usuarios y ataque a credenciales sin
licencias ni imágenes de gran tamaño. El escenario está en el plan de trabajo, no en el repositorio.
