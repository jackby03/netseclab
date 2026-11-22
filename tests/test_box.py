"""Pruebas de la caja: estructura de los scripts y de la semilla.

No se puede construir la caja en este entorno (hace falta Linux con QEMU), así que lo que se
comprueba aquí es que los ingredientes son coherentes: YAML válido, bloques de shell equilibrados y
que el empaquetado lleva lo que el provisionamiento espera.
"""

from __future__ import annotations

import re
import tarfile
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
CAJA = RAIZ / "images" / "box"


def _sin_comentarios(texto: str) -> str:
    return "\n".join(l for l in texto.splitlines() if not l.lstrip().startswith("#"))


def _bloques(texto: str) -> dict[str, int]:
    limpio = _sin_comentarios(texto)
    return {
        "if": len(re.findall(r"(?m)^\s*if\s", limpio)),
        "fi": len(re.findall(r"(?m)^\s*fi\b", limpio)),
        "case": len(re.findall(r"(?m)^\s*case\s", limpio)),
        "esac": len(re.findall(r"(?m)^\s*esac\b", limpio)),
        "do": len(re.findall(r"\bdo\b", limpio)),
        "done": len(re.findall(r"(?m)^\s*done\b", limpio)),
    }


def test_existen_los_ingredientes():
    for nombre in ("build.sh", "provision.sh", "netseclab.vmx", "seed/user-data", "seed/meta-data"):
        assert (CAJA / nombre).is_file(), f"falta images/box/{nombre}"


def test_los_scripts_son_bash():
    assert (CAJA / "build.sh").read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")
    assert (CAJA / "provision.sh").read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")


def test_bloques_de_shell_equilibrados():
    for nombre in ("build.sh", "provision.sh"):
        conteo = _bloques((CAJA / nombre).read_text(encoding="utf-8"))
        assert conteo["if"] == conteo["fi"], (nombre, conteo)
        assert conteo["case"] == conteo["esac"], (nombre, conteo)
        assert conteo["do"] == conteo["done"], (nombre, conteo)


def test_heredocs_cerrados():
    for nombre in ("build.sh", "provision.sh"):
        lineas = (CAJA / nombre).read_text(encoding="utf-8").splitlines()
        abiertos = []
        for linea in lineas:
            m = re.search(r"<<-?'?([A-Za-z_][A-Za-z0-9_]*)'?", linea)
            if m and not linea.lstrip().startswith("#"):
                abiertos.append(m.group(1))
                continue
            if abiertos and linea.strip() == abiertos[-1]:
                abiertos.pop()
        assert abiertos == [], f"{nombre}: heredoc sin cerrar {abiertos}"


def test_la_semilla_es_valida():
    crudo = (CAJA / "seed" / "user-data").read_text(encoding="utf-8")
    assert "__PUBKEY__" in crudo
    datos = yaml.safe_load(crudo.replace("__PUBKEY__", "ssh-ed25519 AAAA prueba"))
    assert datos["hostname"] == "netseclab"
    assert datos["users"][0]["name"] == "lab"
    assert datos["users"][0]["sudo"].startswith("ALL=")

    meta = yaml.safe_load((CAJA / "seed" / "meta-data").read_text(encoding="utf-8"))
    assert meta["local-hostname"] == "netseclab"


def test_el_vmx_no_pide_anidamiento():
    texto = (CAJA / "netseclab.vmx").read_text(encoding="utf-8")
    claves = dict(
        linea.split("=", 1) for linea in texto.splitlines() if "=" in linea and not linea.startswith("#")
    )
    claves = {k.strip(): v.strip().strip('"') for k, v in claves.items()}
    assert claves["displayName"] == "netseclab"
    assert claves["guestOS"].startswith("debian")
    # una sola tarjeta, NAT: la caja no se asoma a la red del anfitrión
    assert claves["ethernet0.connectionType"] == "nat"
    assert "ethernet1.present" not in claves
    # no se exige virtualización anidada
    assert "vhv.enable" not in claves
    assert claves["scsi0:0.fileName"] == "netseclab.vmdk"


def test_el_empaquetado_lleva_lo_que_espera_el_provisionamiento():
    """El tar que crea build.sh y lo que provision.sh espera tienen que cuadrar."""
    build = (CAJA / "build.sh").read_text(encoding="utf-8")
    provision = (CAJA / "provision.sh").read_text(encoding="utf-8")

    assert "tar -C \"$RAIZ\"" in build
    assert "pyproject.toml src lab docs README.md" in build
    assert "tar -C /opt/netseclab -xzf /tmp/netseclab-src.tar.gz" in provision
    # sin --strip-components: el tar no tiene directorio raíz
    assert "--strip-components" not in provision
    assert "PYTHONPATH=/opt/netseclab/src" in provision


def test_el_build_fija_la_version_de_debian():
    build = (CAJA / "build.sh").read_text(encoding="utf-8")
    assert "DEBIAN_BUILD:-2026" in build
    assert "latest" not in build.split("comprobar_entorno")[0] or "no se usa" in build
    assert "sha512sum -c -" in build
