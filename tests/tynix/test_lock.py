"""Lockfile: clavado, lectura, escritura y detección de deriva."""

from __future__ import annotations

import pytest

from tynix.errors import InvalidLockError
from tynix.lock import Lock, read_lock, write_lock
from tynix.manifest import Base, Environment, Package


def _entorno(nombre: str = "node-fw", version: str = "1.1.3-1") -> Environment:
    return Environment(
        name=nombre,
        base=Base(image="debian-13"),
        packages=(Package(name="nftables", version=version),),
    )


def test_un_lock_va_y_vuelve_por_yaml():
    lock = Lock()
    lock.add(_entorno())
    recuperado = Lock.from_yaml(lock.to_yaml())
    assert recuperado.environments["node-fw"].content_hash() == _entorno().content_hash()


def test_el_lock_se_escribe_y_se_lee(tmp_path):
    lock = Lock()
    lock.add(_entorno())
    ruta = write_lock(tmp_path / "tynix.lock", lock)
    assert ruta.exists()
    recuperado = read_lock(ruta)
    assert set(recuperado.environments) == {"node-fw"}


def test_sin_deriva_no_hay_diferencias():
    lock = Lock()
    lock.add(_entorno())
    assert lock.drift(lock) == []


def test_una_version_distinta_es_deriva():
    clavado = Lock()
    clavado.add(_entorno(version="1.1.3-1"))
    actual = Lock()
    actual.add(_entorno(version="1.1.4-1"))
    deriva = clavado.drift(actual)
    assert len(deriva) == 1
    assert deriva[0].kind == "changed"
    assert "1.1.3-1" not in deriva[0].describe()  # describe el hash, no la versión
    assert "changed" in deriva[0].describe()


def test_un_entorno_nuevo_y_uno_que_desaparece():
    clavado = Lock()
    clavado.add(_entorno("viejo"))
    actual = Lock()
    actual.add(_entorno("nuevo"))
    tipos = {(d.environment, d.kind) for d in clavado.drift(actual)}
    assert tipos == {("viejo", "removed"), ("nuevo", "added")}


def test_una_version_de_formato_desconocida_falla():
    with pytest.raises(InvalidLockError, match="unsupported version"):
        Lock.from_dict({"version": 99, "environments": {}})


def test_el_nombre_debe_coincidir_con_su_clave():
    with pytest.raises(InvalidLockError, match="does not match its key"):
        Lock.from_dict(
            {
                "version": 1,
                "environments": {"otro": {"name": "node-fw", "base": {"image": "debian-13"}}},
            }
        )


def test_un_lock_que_no_existe_falla(tmp_path):
    with pytest.raises(InvalidLockError, match="does not exist"):
        read_lock(tmp_path / "no-hay.lock")
