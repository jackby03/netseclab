"""Pruebas de `lab image`: recetas, plan de construcción y CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from lab import cli
from lab.engine import RecordingRunner
from lab.errors import LabErrors
from lab.images import build_plan, load_recipe

RAIZ = Path(__file__).resolve().parents[1]
RECETAS = RAIZ / "images" / "recipes"


def test_las_recetas_del_repositorio_cargan():
    rutas = sorted(RECETAS.glob("*.yaml"))
    assert len(rutas) >= 2
    for ruta in rutas:
        receta = load_recipe(ruta)
        assert receta.name
        assert receta.referencia.startswith("lab/")
        assert receta.instancia.startswith("lab-build-")


def test_el_plan_de_construccion_esta_ordenado():
    receta = load_recipe(RECETAS / "attacker.yaml")
    pasos = build_plan(receta)
    fases = []
    for paso in pasos:
        if not fases or fases[-1] != paso.phase:
            fases.append(paso.phase)
    assert fases[0] == "limpiar"
    assert fases[-1] == "limpiar"
    assert "crear" in fases and "paquetes" in fases and "publicar" in fases


def test_la_imagen_se_publica_con_alias():
    receta = load_recipe(RECETAS / "web.yaml")
    comandos = [p.command() for p in build_plan(receta) if p.kind == "cmd"]
    assert any("incus publish lab-build-web --alias lab/web:1" in c for c in comandos)
    # se publica con la instancia parada y luego se borra
    assert any(c.endswith("incus stop lab-build-web") for c in comandos)
    assert any("incus delete lab-build-web --force" in c for c in comandos)


def test_los_assets_de_la_receta_existen():
    receta = load_recipe(RECETAS / "web.yaml")
    assert receta.assets, "la receta web debería copiar una página"
    build_plan(receta)  # no debe lanzar FileNotFoundError


def test_una_receta_con_clave_desconocida_falla(workdir):
    ruta = workdir / "rara.yaml"
    ruta.write_text("name: rara\nbase: debian13\npaquetes: [nmap]\n", encoding="utf-8")
    with pytest.raises(LabErrors, match="unknown key"):
        load_recipe(ruta)


def test_una_receta_sin_nombre_falla(workdir):
    ruta = workdir / "sinnombre.yaml"
    ruta.write_text("base: debian13\n", encoding="utf-8")
    with pytest.raises(LabErrors, match="name"):
        load_recipe(ruta)


def test_cli_build_dry_run(monkeypatch, capsys):
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    codigo = cli.main(["image", "build", str(RECETAS / "attacker.yaml"), "--dry-run"])
    assert codigo == 0
    salida = capsys.readouterr().out
    assert "lab/attacker:1" in salida
    assert "incus launch" in salida


def test_cli_build_ejecuta(monkeypatch, capsys):
    runner = RecordingRunner()
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    codigo = cli.main(["image", "build", str(RECETAS / "attacker.yaml")])
    assert codigo == 0
    assert runner.contiene("incus publish lab-build-attacker --alias lab/attacker:1")
    assert "lab/attacker:1" in capsys.readouterr().out


def test_cli_ls(monkeypatch, capsys):
    runner = RecordingRunner({"image list": (0, "lab/web:1\nlab/attacker:1\nother\n", "")})
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    assert cli.main(["image", "ls"]) == 0
    salida = capsys.readouterr().out
    assert "lab/web:1" in salida and "lab/attacker:1" in salida
    assert "other" not in salida
