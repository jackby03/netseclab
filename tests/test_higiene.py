"""Comprobaciones de higiene del repositorio."""

from __future__ import annotations

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


def test_hay_gitattributes_para_no_romper_los_scripts():
    texto = (RAIZ / ".gitattributes").read_text(encoding="utf-8")
    assert "*.sh text eol=lf" in texto
    assert "*.py text eol=lf" in texto


def test_ningun_fichero_de_texto_tiene_finales_de_linea_windows():
    """Un CRLF en un .sh deja el shebang y `set -o pipefail` inservibles en Linux."""
    extensiones = {".py", ".yaml", ".yml", ".sh", ".md", ".toml", ".vmx", ".nft", ".rules"}
    culpables = []
    for carpeta in ("src", "lab", "images", "tests", "docs", ".github"):
        base = RAIZ / carpeta
        if not base.exists():
            continue
        for ruta in base.rglob("*"):
            if ruta.is_file() and ruta.suffix in extensiones and b"\r\n" in ruta.read_bytes():
                culpables.append(str(ruta.relative_to(RAIZ)))
    assert culpables == [], f"ficheros con CRLF: {culpables}"


def test_gitignore_no_deja_entrar_artefactos():
    texto = (RAIZ / ".gitignore").read_text(encoding="utf-8")
    for patron in ("build/", "*.qcow2", "answers/", "capture/", "__pycache__/"):
        assert patron in texto


def test_hay_workflow_de_ci():
    ci = RAIZ / ".github" / "workflows" / "ci.yml"
    assert ci.is_file()
    texto = ci.read_text(encoding="utf-8")
    assert "pytest" in texto
    assert "lab validate" in texto


def test_hay_documentacion_de_contribucion_y_cambios():
    assert (RAIZ / "CONTRIBUTING.md").is_file()
    assert (RAIZ / "CHANGELOG.md").is_file()


def test_el_trabajo_pendiente_esta_documentado():
    """Lo que queda por hacer vive en CONTRIBUTING, no en la documentación."""
    contrib = RAIZ / "CONTRIBUTING.md"
    assert contrib.is_file()
    texto = contrib.read_text(encoding="utf-8")
    assert "Trabajo pendiente" in texto
    assert "make box" in texto


def test_la_licencia_esta_completa():
    licencia = RAIZ / "LICENSE"
    if not licencia.exists():
        pytest.skip("LICENSE todavía no está")
    texto = licencia.read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in texto
    assert "Version 3, 29 June 2007" in texto
    assert len(texto.splitlines()) > 500
    assert "END OF TERMS AND CONDITIONS" in texto
