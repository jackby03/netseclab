"""Comprobaciones de higiene del repositorio."""

from __future__ import annotations

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


def test_hay_gitattributes_para_no_romper_los_scripts():
    texto = (RAIZ / ".gitattributes").read_text(encoding="utf-8")
    assert "*.sh text eol=lf" in texto
    assert "*.py text eol=lf" in texto


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


def test_hay_lista_de_pendientes_humanos():
    doc = RAIZ / "docs" / "06-pendientes-humanos.md"
    assert doc.is_file()
    texto = doc.read_text(encoding="utf-8")
    # lo que de verdad no se puede hacer sin una persona
    assert "make box" in texto
    assert "PTY" in texto


def test_la_licencia_esta_completa():
    licencia = RAIZ / "LICENSE"
    if not licencia.exists():
        pytest.skip("LICENSE todavía no está; ver docs/06-pendientes-humanos.md")
    texto = licencia.read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in texto
    assert "Version 3, 29 June 2007" in texto
    assert len(texto.splitlines()) > 500
    assert "END OF TERMS AND CONDITIONS" in texto
