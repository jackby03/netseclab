"""`lab gc`: borrar las imágenes que ningún laboratorio referencia."""

from __future__ import annotations

from pathlib import Path

from lab import cli
from lab.engine import RecordingRunner

EJEMPLO = Path(__file__).resolve().parent.parent / "lab" / "examples" / "example.net.yaml"


def _runner(aliases: list[str]) -> RecordingRunner:
    csv = "aliases\n" + "\n".join(aliases) + "\n"
    return RecordingRunner(
        {
            "image list": (0, csv, ""),
            "image delete": (0, "", ""),
        }
    )


def _preparar(monkeypatch, aliases: list[str]) -> RecordingRunner:
    runner = _runner(aliases)
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    return runner


def test_sin_decir_que_conservar_no_borra_nada(monkeypatch, capsys):
    runner = _preparar(monkeypatch, ["lab-node-v1"])
    assert cli.main(["gc"]) == 2
    assert "Nothing is deleted" in capsys.readouterr().err
    assert runner.calls == []


def test_sin_yes_solo_ensena_lo_que_borraria(monkeypatch, capsys):
    runner = _preparar(monkeypatch, ["lab-node-v1", "lab-web-v1", "lab-vieja-v1"])
    assert cli.main(["gc", str(EJEMPLO)]) == 0
    salida = capsys.readouterr().out
    assert "lab-vieja-v1" in salida
    assert "nothing deleted" in salida
    assert not runner.contiene("image delete")


def test_con_yes_borra_solo_lo_que_sobra(monkeypatch, capsys):
    runner = _preparar(monkeypatch, ["lab-node-v1", "lab-web-v1", "lab-vieja-v1"])
    assert cli.main(["gc", str(EJEMPLO), "--yes"]) == 0
    salida = capsys.readouterr().out
    assert "1 images deleted" in salida
    assert runner.contiene("image delete lab-vieja-v1")
    assert not runner.contiene("image delete lab-node-v1")


def test_keep_protege_una_imagen(monkeypatch, capsys):
    runner = _preparar(monkeypatch, ["lab-node-v1", "lab-web-v1", "lab-otra-v1"])
    assert cli.main(["gc", str(EJEMPLO), "--keep", "lab-otra-v1", "--yes"]) == 0
    assert "0 images deleted" in capsys.readouterr().out or not runner.contiene(
        "image delete lab-otra-v1"
    )


def test_no_toca_imagenes_de_fuera(monkeypatch, capsys):
    runner = _preparar(monkeypatch, ["lab-node-v1", "lab-web-v1", "ubuntu", "debian-13"])
    cli.main(["gc", str(EJEMPLO), "--yes"])
    assert not runner.contiene("image delete ubuntu")
    assert not runner.contiene("image delete debian-13")
