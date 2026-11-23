"""Manifiesto de entorno: contenido clavado y direccionado por hash."""

from __future__ import annotations

import pytest

from tynix.errors import InvalidLockError
from tynix.manifest import Base, Environment, FileEntry, Package


def _entorno(**cambios) -> Environment:
    base = {
        "name": "node-fw",
        "base": Base(image="debian-13", fingerprint="9f2c" * 8),
        "packages": (
            Package(name="nftables", version="1.1.3-1", sha256="aa" * 32),
            Package(name="suricata", version="7.0.10-1", sha256="bb" * 32),
        ),
        "files": (FileEntry(path="/etc/lab/fw.nft", sha256="cc" * 32),),
        "startup": ("systemctl enable nftables",),
    }
    base.update(cambios)
    return Environment(**base)


def test_el_hash_no_depende_del_orden_de_los_paquetes():
    uno = _entorno(
        packages=(
            Package(name="nftables", version="1.1.3-1", sha256="aa" * 32),
            Package(name="suricata", version="7.0.10-1", sha256="bb" * 32),
        )
    )
    otro = _entorno(
        packages=(
            Package(name="suricata", version="7.0.10-1", sha256="bb" * 32),
            Package(name="nftables", version="1.1.3-1", sha256="aa" * 32),
        )
    )
    assert uno.content_hash() == otro.content_hash()


def test_cambiar_una_version_cambia_el_hash():
    original = _entorno()
    nueva = _entorno(
        packages=(
            Package(name="nftables", version="1.1.4-1", sha256="aa" * 32),
            Package(name="suricata", version="7.0.10-1", sha256="bb" * 32),
        )
    )
    assert original.content_hash() != nueva.content_hash()


def test_el_nombre_de_imagen_es_direccionado_por_contenido():
    entorno = _entorno()
    nombre = entorno.image_name()
    assert nombre.startswith("tynix-node-fw-")
    assert nombre.endswith(entorno.content_hash()[:12])
    # mismo contenido, mismo nombre, en cualquier máquina
    assert _entorno().image_name() == nombre


def test_un_fichero_distinto_cambia_el_hash():
    original = _entorno()
    otro = _entorno(files=(FileEntry(path="/etc/lab/fw.nft", sha256="dd" * 32),))
    assert original.content_hash() != otro.content_hash()


def test_el_manifiesto_va_y_vuelve():
    entorno = _entorno()
    recuperado = Environment.from_dict(entorno.to_dict(), "entorno")
    assert recuperado == entorno
    assert recuperado.content_hash() == entorno.content_hash()


def test_un_entorno_sin_base_falla():
    with pytest.raises(InvalidLockError, match="base needs at least 'image'"):
        Environment.from_dict({"name": "x"}, "entorno")


def test_un_paquete_sin_nombre_falla():
    with pytest.raises(InvalidLockError, match="a package needs at least 'name'"):
        Environment.from_dict(
            {"name": "x", "base": {"image": "debian-13"}, "packages": [{}]}, "entorno"
        )
