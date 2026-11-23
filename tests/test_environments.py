"""Entornos declarados por los nodos: resolución, construcción y lock."""

from __future__ import annotations

from pathlib import Path

import pytest

from lab import cli, environments
from lab.errors import LabErrors
from lab.model import load
from lab.plan import build
from tynix import read_lock

RUTA_IMAGENES = Path(__file__).resolve().parent.parent / "lab" / "images.yaml"


def _topologia(tmp_path: Path, nodos: str) -> Path:
    ruta = tmp_path / "lab.yaml"
    ruta.write_text(
        f"""version: 1
name: pruebas
networks:
  ext: {{ cidr: 10.30.0.0/24 }}
nodes:
{nodos}
""",
        encoding="utf-8",
        newline="\n",
    )
    return ruta


CON_ENVOLTORIO = """  - name: fw
    environment:
      base: debian13
      packages: [nftables, suricata]
    links: [{ net: ext, ip: 10.30.0.10 }]
"""

FUZZ = """{
  "clave": "entorno",
  "entorno": {"base": "debian13", "packages": ["nftables"]}
}"""


def test_un_nodo_puede_declarar_un_entorno(tmp_path):
    topo = load(_topologia(tmp_path, CON_ENVOLTORIO))
    nodo = topo.node("fw")
    assert nodo is not None
    assert nodo.environment is not None
    assert nodo.environment.base == "debian13"
    assert nodo.environment.packages == ["nftables", "suricata"]


def test_imagen_y_entorno_juntos_es_un_error(tmp_path):
    nodos = """  - name: fw
    image: debian13
    environment: {base: debian13}
    links: [{ net: ext }]
"""
    with pytest.raises(LabErrors, match="cannot be combined"):
        load(_topologia(tmp_path, nodos))


def test_un_entorno_sin_base_es_un_error(tmp_path):
    nodos = """  - name: fw
    environment: {packages: [nftables]}
    links: [{ net: ext }]
"""
    with pytest.raises(LabErrors, match="required"):
        load(_topologia(tmp_path, nodos))


def test_una_clave_desconocida_en_el_entorno_avisa(tmp_path):
    nodos = """  - name: fw
    environment: {base: debian13, paquetes: [nftables]}
    links: [{ net: ext }]
"""
    with pytest.raises(LabErrors, match="unknown key"):
        load(_topologia(tmp_path, nodos))


def test_el_nombre_de_imagen_es_estable_y_depende_de_los_paquetes(tmp_path):
    topo = load(_topologia(tmp_path, CON_ENVOLTORIO))
    nodo = topo.node("fw")
    assert nodo is not None
    catalogo = {"debian13": "lab-node-v1"}
    primera = environments.image_for(nodo, catalogo)
    assert primera.startswith("lab-env-")
    assert environments.image_for(nodo, catalogo) == primera
    nodo.environment.packages = ["nftables"]
    assert environments.image_for(nodo, catalogo) != primera


def test_dos_nodos_con_el_mismo_entorno_comparten_imagen(tmp_path):
    nodos = """  - name: a
    environment: {base: debian13, packages: [curl]}
    links: [{ net: ext }]
  - name: b
    environment: {base: debian13, packages: [curl]}
    links: [{ net: ext }]
"""
    topo = load(_topologia(tmp_path, nodos))
    catalogo = {"debian13": "lab-node-v1"}
    assert environments.image_for(topo.node("a"), catalogo) == environments.image_for(
        topo.node("b"), catalogo
    )


def test_el_paso_de_construccion_es_idempotente(tmp_path):
    topo = load(_topologia(tmp_path, CON_ENVOLTORIO))
    nodo = topo.node("fw")
    paso = environments.ensure_step(nodo, {"debian13": "lab-node-v1"})
    assert paso is not None
    guion = paso.command()
    assert "incus image info" in guion
    assert "apt-get install" in guion
    assert "incus publish" in guion
    assert "user.tynix.manifest" in guion


def test_el_plan_usa_la_imagen_del_entorno_y_la_construye_antes(tmp_path):
    topo = load(_topologia(tmp_path, CON_ENVOLTORIO))
    plan = build(topo)
    imagen = next(n.image for n in plan.nodes if n.name == "fw")
    assert imagen.startswith("lab-env-")

    fases = [paso.phase for paso in plan.steps]
    assert "entorno" in fases
    indice_entorno = fases.index("entorno")
    indice_nodo = fases.index("node")
    assert indice_entorno < indice_nodo


def test_el_lock_clava_los_entornos(tmp_path, monkeypatch, capsys):
    ruta = _topologia(tmp_path, CON_ENVOLTORIO)
    destino = tmp_path / "lab.lock"
    assert cli.main(["lock", str(ruta), "--out", str(destino)]) == 0
    lock = read_lock(destino)
    assert list(lock.environments) == [environments.ENV_NAME]
    assert "1 environments locked" in capsys.readouterr().out


def test_lock_detecta_la_deriva(tmp_path, capsys):
    ruta = _topologia(tmp_path, CON_ENVOLTORIO)
    destino = tmp_path / "lab.lock"
    cli.main(["lock", str(ruta), "--out", str(destino)])
    assert cli.main(["lock", str(ruta), "--out", str(destino), "--check"]) == 0

    # cambia el entorno: el lock ya no coincide
    ruta.write_text(
        ruta.read_text(encoding="utf-8").replace("[nftables, suricata]", "[nftables]"),
        encoding="utf-8",
        newline="\n",
    )
    assert cli.main(["lock", str(ruta), "--out", str(destino), "--check"]) == 1
    assert "changed" in capsys.readouterr().out


def test_una_topologia_sin_entornos_no_genera_lock(tmp_path, capsys):
    nodos = """  - name: fw
    image: debian13
    links: [{ net: ext }]
"""
    ruta = _topologia(tmp_path, nodos)
    assert cli.main(["lock", str(ruta), "--out", str(tmp_path / "lab.lock")]) == 2
    assert "no environments" in capsys.readouterr().err
