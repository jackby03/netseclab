"""Almacén de entornos: faltantes y basura."""

from __future__ import annotations

from tynix.manifest import Base, Environment, Package
from tynix.store import ImageStore, garbage, image_name, missing, referenced


def _entorno(nombre: str = "node-fw", version: str = "1.1.3-1") -> Environment:
    return Environment(
        name=nombre,
        base=Base(image="debian-13"),
        packages=(Package(name="nftables", version=version),),
    )


class _Almacen:
    def __init__(self, nombres: list[str]) -> None:
        self._nombres = list(nombres)
        self.borrados: list[str] = []

    def names(self) -> list[str]:
        return list(self._nombres)

    def exists(self, name: str) -> bool:
        return name in self._nombres

    def delete(self, name: str) -> None:
        self.borrados.append(name)
        self._nombres.remove(name)


def test_el_almacen_falso_cumple_el_protocolo():
    assert isinstance(_Almacen([]), ImageStore)


def test_lo_que_falta_es_lo_que_no_esta():
    entorno = _entorno()
    vacio = _Almacen([])
    assert missing([entorno], vacio) == [entorno]
    lleno = _Almacen([image_name(entorno)])
    assert missing([entorno], lleno) == []


def test_referenciadas_son_los_nombres_direccionados():
    entorno = _entorno()
    assert referenced([entorno]) == {entorno.image_name()}


def test_la_basura_solo_mira_sus_prefijos():
    disponibles = ["tynix-a-111", "tynix-b-222", "otra-cosa", "lab-node-v1"]
    sobrantes = garbage(disponibles, keep={"tynix-b-222"})
    assert sobrantes == ["tynix-a-111"]


def test_se_pueden_gestionar_varios_prefijos():
    disponibles = ["lab-node-v1", "lab-web-v1", "lab/node:1", "ubuntu"]
    sobrantes = garbage(disponibles, keep={"lab-node-v1"}, prefixes=("lab-", "lab/"))
    assert sobrantes == ["lab-web-v1", "lab/node:1"]


def test_cambiar_la_version_deja_la_anterior_como_basura():
    viejo = _entorno(version="1.1.3-1")
    nuevo = _entorno(version="1.1.4-1")
    disponibles = [image_name(viejo), image_name(nuevo)]
    sobrantes = garbage(disponibles, keep=referenced([nuevo]))
    assert sobrantes == [image_name(viejo)]
