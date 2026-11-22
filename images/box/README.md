# La caja

El artefacto que se importa en VMware: un Debian 13 mínimo con Incus, el CLI del laboratorio y las
imágenes base cacheadas, para que funcione **sin Internet**.

## Qué contiene

| | |
|---|---|
| SO | Debian 13 (trixie), sin escritorio |
| Tamaño | **1,9 GB** el `.tar.gz` (3,3 GB el `.vmdk` descomprimido) |
| Disco | 12 GB, de los que usa ~3 GB |
| RAM | 2 GB (sube a 4 GB para el perfil `full` con 7 nodos) |
| Incus | 4 imágenes de nodo con las herramientas dentro |
| CLI | `/usr/local/bin/lab` |
| Paquetes | cacheados en `/var/cache/apt` |
| Red | NAT de VMware, un solo adaptador (`vmxnet3`) |
| Anidamiento | **ninguno**: los nodos son contenedores |

> El tamaño depende de `discard=unmap` y `fstrim` al apagar: sin eso el qcow2
> conserva los bloques liberados y el artefacto sale de 4,5 GB en vez de 1,9.

## Construirla

Requiere un anfitrión Linux x86_64 con QEMU, o WSL2.

```bash
./images/box/build.sh              # imagen + provisión + VMDK (~15 min)
./images/box/build.sh imagen       # solo el qcow2 provisionado
./images/box/build.sh vmdk         # solo la conversión
```

Resultado en `build/box/`:

- `netseclab.qcow2` — para QEMU/libvirt
- `netseclab-vmware.tar.gz` — `netseclab.vmx` + `netseclab.vmdk`, se abre directamente en VMware
  Workstation o Player

La versión de Debian está fijada (`DEBIAN_BUILD`), no se usa `latest`: el build es reproducible y el
checksum de la imagen base se verifica.

## Usarla

1. Descomprime `netseclab-vmware.tar.gz` y abre `netseclab.vmx` con VMware.
2. Entra por la consola de VMware con el usuario **`lab`** y la contraseña **`netseclab`**.
   Cámbiala en cuanto arranques: `passwd`.
3. `lab --help`.

### Credenciales

| Dónde | Usuario | Contraseña |
|---|---|---|
| La caja (consola de VMware) | `lab` | `netseclab` |
| Los nodos del laboratorio | `root` | `netseclab` |
| Los nodos del laboratorio | `user1` | `netseclab` |

`user1` es el usuario no privilegiado con `sudo`, igual que en el NETinVM original. El SSH de los
nodos acepta contraseña, para que las prácticas de SSH funcionen. La caja, en cambio, solo acepta
clave.

El SSH está configurado solo con clave: la contraseña sirve para la consola, no para la red. La
clave pública que autoriza el acceso es la que se genera durante la construcción
(`build/box/id_ed25519`).

```bash
lab up /opt/netseclab/lab/examples/fuzz-evasion.yaml
lab status
lab check /opt/netseclab/lab/exercises/06-fuzz-evasion.yaml
```

## Lo que la caja **no** hace

- No expone los nodos a la red del anfitrión: están en bridges internos de Incus.
- No usa virtualización anidada, así que funciona en cualquier portátil que mueva VMware.
- No incluye escritorio. Las consolas se abren con `lab console <nodo>` o con `lab web`, que sirve
  una pestaña por nodo en el navegador del anfitrión.

## Seguridad

La caja es la frontera: dentro hay un laboratorio pensado para atacar máquinas, y comparte kernel
entre nodos. **No la uses como servidor**, no le des más interfaces que la NAT y trata el fichero de
la VM como material didáctico, no como infraestructura.
