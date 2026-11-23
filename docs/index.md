# netseclab

Esta página es la portada de la documentación: explica qué es el proyecto y ordena el resto de las
páginas.

`netseclab` es un laboratorio de seguridad en redes ligero, declarativo y reproducible. Una máquina
virtual —la **caja**— contiene Incus y las imágenes de nodo; los nodos del escenario son contenedores
de sistema con `systemd`, `sshd`, `apache`, `nftables`, `nmap` y `tcpdump`. El laboratorio se describe
en YAML y el CLI `lab` lo levanta, lo fotografía, lo restaura y corrige los ejercicios.

## Empieza aquí

| Si quieres… | Lee |
|---|---|
| Tener un laboratorio en marcha | [Primeros pasos](getting-started.md) |
| Entender el vocabulario del proyecto | [Taxonomía](concepts/taxonomy.md) |
| Usar el laboratorio en clase | [Operación](guides/operating.md) |
| Escribir o corregir un ejercicio | [Ejercicios](guides/exercises.md) |
| Compartir un laboratorio con otras personas | [Distribución](guides/sharing.md) |
| Consultar el formato YAML | [Topología](reference/topology.md) |
| Consultar un comando del CLI | [CLI](reference/cli.md) |
| Consultar imágenes y toolsets | [Imágenes](reference/images.md) |
| Entender cómo funciona por dentro | [Arquitectura](concepts/architecture.md) |
| Conocer el origen y las diferencias con NETinVM | [Origen](design/origins.md) |

## Cómo se organiza

| Sección | Contenido |
|---|---|
| Primeros pasos | Instalación de la caja, primer `lab up` y primer ejercicio |
| Conceptos | Piezas del modelo y arquitectura interna |
| Guías | Operación diaria, escritura de ejercicios y distribución |
| Referencia | Formato de topología, comandos y catálogo de imágenes |
| Diseño | Procedencia del proyecto y decisiones que lo separan de NETinVM |

!!! note "Estado"
    La versión actual es la **0.2.0**. Están implementados el ciclo de vida, los ejercicios, las
    consolas, la captura, los entornos reproducibles de tynix, la caché de imágenes y los paquetes
    `.labpack`. La firma de paquetes, la salida a Internet declarada, las herramientas por nodo y los
    nodos Windows están pendientes.

## Licencia

El código se distribuye con GPL-3.0-or-later y la documentación y los ejercicios con CC-BY-SA-4.0.
Los textos completos están en `LICENSE` y `LICENSES/CC-BY-SA-4.0.txt`, en la raíz del repositorio.
