"""Respuestas estrictas: un valor concreto, comparado por hash."""

from __future__ import annotations

from pathlib import Path

import pytest

from lab import cli
from lab.answers import Answer, digest, normalize, read_submitted, save_submitted
from lab.errors import LabErrors
from lab.exercise import load

EJEMPLOS = Path(__file__).resolve().parent.parent / "lab" / "examples"
LAB = EJEMPLOS / "example.net.yaml"


def _ejercicio(workdir: Path, texto: str) -> Path:
    ruta = workdir / "ej.yaml"
    ruta.write_text(texto, encoding="utf-8", newline="\n")
    return ruta


def _con_respuestas(workdir: Path, extra: str = "") -> Path:
    return _ejercicio(
        workdir,
        f"""id: prueba
title: Prueba
lab: {LAB}
answers:
  - id: ip
    question: "¿Qué IP tenía en el segmento de administración?"
    points: 5
    hash: {digest('10.5.0.10')}
  - id: usuario
    question: "¿Qué usuario permite sesión anónima?"
    points: 10
    value: anonymous
report:
  - "Explica cómo llegaste hasta ahí."
{extra}""",
    )


# --------------------------------------------------------------------------- normalización


def test_la_comparacion_ignora_mayusculas_espacios_y_comillas():
    assert normalize("  10.5.0.10  ") == "10.5.0.10"
    assert normalize("User-Agent") == "user-agent"
    assert normalize('"anonymous"') == "anonymous"
    assert normalize("  Grupo   Romero  ") == "grupo romero"


def test_el_hash_no_depende_del_formato():
    assert digest("Anonymous") == digest("  anonymous  ")
    assert digest("443") != digest("443/tcp")


def test_una_respuesta_acepta_solo_su_valor():
    respuesta = Answer(id="x", question="?", hashes=[digest("443")])
    assert respuesta.accepts("443")
    assert respuesta.accepts(" 443 ")
    assert not respuesta.accepts("443/tcp")
    assert not respuesta.accepts("")
    assert not respuesta.accepts("reject")


def test_las_variantes_se_declaran_y_no_se_adivinan():
    respuesta = Answer(
        id="x", question="?", hashes=[digest("10.5.0.10"), digest("10.5.0.10/24")]
    )
    assert respuesta.accepts("10.5.0.10/24")  # variante declarada
    assert not respuesta.accepts("10.5.0.10/32")  # no declarada: no se adivina


# --------------------------------------------------------------------------- carga


def test_un_ejercicio_con_respuestas_calcula_los_puntos(workdir):
    ejercicio = load(_con_respuestas(workdir))
    assert ejercicio.points == 15
    assert [a.id for a in ejercicio.answers] == ["ip", "usuario"]
    assert ejercicio.report == ["Explica cómo llegaste hasta ahí."]


def test_el_valor_en_claro_se_detecta(workdir):
    ejercicio = load(_con_respuestas(workdir))
    assert ejercicio.reveals_answers  # por el `value: anonymous`


def test_una_respuesta_sin_hash_ni_valor_falla(workdir):
    ruta = _ejercicio(
        workdir,
        f"""id: x
title: X
lab: {LAB}
answers:
  - id: a
    question: "¿?"
""",
    )
    with pytest.raises(LabErrors, match="needs 'hash'"):
        load(ruta)


def test_dos_respuestas_con_el_mismo_id_fallan(workdir):
    ruta = _ejercicio(
        workdir,
        f"""id: x
title: X
lab: {LAB}
answers:
  - {{ id: a, question: "¿?", hash: {digest('uno')} }}
  - {{ id: a, question: "¿?", hash: {digest('otro')} }}
""",
    )
    with pytest.raises(LabErrors, match="duplicated"):
        load(ruta)


def test_la_pregunta_puede_estar_en_cualquier_idioma(workdir):
    """El texto es contenido libre; la estricta es la respuesta."""
    ruta = _ejercicio(
        workdir,
        f"""id: x
title: X
lab: {LAB}
answers:
  - {{ id: a, question: "Why does the firewall reject 443?", hash: {digest('reject')} }}
""",
    )
    ejercicio = load(ruta)
    assert ejercicio.answers[0].accepts("reject")


# --------------------------------------------------------------------------- guardado


def test_las_respuestas_se_guardan_como_json(workdir):
    ruta = save_submitted("prueba", "ip", "10.5.0.10", base=workdir)
    assert ruta.name == "prueba.json"
    assert read_submitted("prueba", base=workdir) == {"ip": "10.5.0.10"}


def test_lab_hash_imprime_el_sha256(capsys):
    assert cli.main(["hash", "443"]) == 0
    assert digest("443") in capsys.readouterr().out


# --------------------------------------------------------------------------- CLI


def test_check_puntua_solo_lo_correcto(workdir, monkeypatch, capsys):
    monkeypatch.chdir(workdir)
    ruta = _con_respuestas(workdir)
    assert cli.main(["answer", str(ruta), "ip", "10.5.0.10"]) == 0
    assert cli.main(["answer", str(ruta), "usuario", "sin contraseña"]) == 0
    codigo = cli.main(["check", str(ruta)])
    salida = capsys.readouterr().out
    assert codigo == 1
    assert "1/2 answers correct - 5/15 points" in salida
    assert "[OK  ]" in salida
    assert "[FAIL]" in salida


def test_check_completo_devuelve_cero(workdir, monkeypatch):
    monkeypatch.chdir(workdir)
    ruta = _con_respuestas(workdir)
    cli.main(["answer", str(ruta), "ip", "10.5.0.10"])
    cli.main(["answer", str(ruta), "usuario", "ANONYMOUS"])
    assert cli.main(["check", str(ruta)]) == 0


def test_report_genera_la_plantilla(workdir, monkeypatch, capsys):
    monkeypatch.chdir(workdir)
    ruta = _con_respuestas(workdir)
    cli.main(["answer", str(ruta), "ip", "10.5.0.10"])
    assert cli.main(["report", str(ruta)]) == 0
    salida = capsys.readouterr().out
    assert "# Prueba" in salida
    assert "10.5.0.10" in salida
    assert "Explica cómo llegaste hasta ahí." in salida
    assert "Student:" in salida


def test_report_se_puede_escribir_a_un_fichero(workdir, monkeypatch):
    monkeypatch.chdir(workdir)
    ruta = _con_respuestas(workdir)
    destino = workdir / "informe.md"
    assert cli.main(["report", str(ruta), "--out", str(destino)]) == 0
    assert "Answers" in destino.read_text(encoding="utf-8")
