"""Pruebas del CLI: validación, render, ciclo de vida y corrección de ejercicios."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab import cli
from lab.engine import RecordingRunner

SNAPS_INITIAL = json.dumps([{"name": "initial"}])
SNAPS_OTRO = json.dumps([{"name": "otro"}])

EJEMPLOS = Path(__file__).resolve().parents[1] / "lab" / "examples"
EJERCICIO = Path(__file__).resolve().parents[1] / "lab" / "exercises" / "06-fuzz-evasion.yaml"


def test_validate_ok(capsys):
    assert cli.main(["validate", str(EJEMPLOS / "example.net.yaml")]) == 0
    salida = capsys.readouterr().out
    assert "OK" in salida and "7 nodes" in salida


def test_validate_detecta_errores(workdir, capsys):
    ruta = workdir / "rota.yaml"
    ruta.write_text("version: 1\nname: rota\nnetworks: {}\nnodes: []\n", encoding="utf-8")
    assert cli.main(["validate", str(ruta)]) == 1
    assert "NOT VALID" in capsys.readouterr().err


def test_render_json(capsys):
    assert cli.main(["render", str(EJEMPLOS / "fuzz-evasion.yaml"), "--format", "json"]) == 0
    datos = json.loads(capsys.readouterr().out)
    assert datos["lab"] == "fuzz-evasion"
    assert [n["name"] for n in datos["nodes"]] == ["evil1", "fw", "www"]


def test_render_table(capsys):
    assert (
        cli.main(
            ["render", str(EJEMPLOS / "example.net.yaml"), "--profile", "mini", "--format", "table"]
        )
        == 0
    )
    salida = capsys.readouterr().out
    assert "NETWORKS" in salida and "NODES" in salida
    assert "mini" in salida


def test_render_escribe_ficheros(workdir):
    assert cli.main(["render", str(EJEMPLOS / "example.net.yaml"), "--out", str(workdir)]) == 0
    assert (workdir / "lab.sh").exists()
    assert (workdir / "plan.json").exists()
    assert (workdir / "fw" / "usr" / "local" / "sbin" / "lab-net").exists()


def test_up_dry_run_no_necesita_incus(capsys):
    assert cli.main(["up", str(EJEMPLOS / "fuzz-evasion.yaml"), "--dry-run"]) == 0
    salida = capsys.readouterr().out
    assert "fuzz-evasion" in salida
    assert "incus network create" in salida


def test_perfil_inexistente(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["up", str(EJEMPLOS / "example.net.yaml"), "--profile", "noexiste", "--dry-run"])
    assert exc.value.code == 2
    assert "does not exist" in capsys.readouterr().err


def test_images_y_toolsets(capsys):
    assert cli.main(["images"]) == 0
    assert "debian13" in capsys.readouterr().out
    assert cli.main(["toolsets"]) == 0
    assert "webfuzz" in capsys.readouterr().out


def test_init_crea_plantilla(workdir, monkeypatch):
    monkeypatch.chdir(workdir)
    assert cli.main(["init", "milab"]) == 0
    ruta = workdir / "milab" / "topology.yaml"
    assert ruta.exists()
    assert "name: milab" in ruta.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- ciclo de vida


def _runner_feliz() -> RecordingRunner:
    return RecordingRunner(
        {
            "snapshot list": (0, "", ""),
            "ping": (0, "", ""),
            "/dev/tcp": (0, "", ""),
            "curl": (0, "200", ""),
            "test -e": (0, "", ""),
            "grep": (0, "0\n", ""),
        }
    )


def test_up_con_runner_simulado(monkeypatch, capsys):
    runner = _runner_feliz()
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    codigo = cli.main(["up", str(EJEMPLOS / "fuzz-evasion.yaml")])
    salida = capsys.readouterr().out
    assert codigo == 0
    assert "snapshot 'initial' created" in salida
    assert runner.contiene("incus network create nvm-ext")
    assert runner.contiene("snapshot create evil1 initial")


def test_up_informa_de_los_fallos(monkeypatch, capsys):
    runner = RecordingRunner({"network create": (1, "", "permiso denegado")})
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    assert cli.main(["up", str(EJEMPLOS / "fuzz-evasion.yaml")]) == 1
    assert "failed" in capsys.readouterr().err


def test_reset_sin_snapshot_avisa(monkeypatch, capsys):
    runner = RecordingRunner({"snapshot list": (0, "otro\n", "")})
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    assert cli.main(["reset", str(EJEMPLOS / "fuzz-evasion.yaml")]) == 1
    assert "snapshot 'initial' does not exist" in capsys.readouterr().err


def test_reset_restaura(monkeypatch, capsys):
    runner = RecordingRunner({"incus query": (0, SNAPS_INITIAL, "")})
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    assert cli.main(["reset", str(EJEMPLOS / "fuzz-evasion.yaml")]) == 0
    assert runner.contiene("snapshot restore evil1 initial")
    assert "restored" in capsys.readouterr().out


def test_capture_red_desconocida(capsys):
    assert cli.main(["capture", str(EJEMPLOS / "fuzz-evasion.yaml"), "--net", "noexiste"]) == 2
    assert "does not exist" in capsys.readouterr().err


def test_capture_se_ejecuta(monkeypatch, capsys, workdir):
    runner = RecordingRunner({"tcpdump": (124, "", "")})
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    destino = workdir / "ext.pcap"
    codigo = cli.main(
        [
            "capture",
            str(EJEMPLOS / "fuzz-evasion.yaml"),
            "--net",
            "ext",
            "--seconds",
            "3",
            "--out",
            str(destino),
        ]
    )
    assert codigo == 0
    assert runner.contiene("tcpdump")
    assert str(destino) in capsys.readouterr().out


# --------------------------------------------------------------------------- ejercicios


def test_check_superado(monkeypatch, capsys, workdir):
    monkeypatch.chdir(workdir)
    monkeypatch.setattr(cli, "_runner", _runner_feliz)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    (workdir / "answers").mkdir()
    (workdir / "answers" / "06-fuzz-evasion.json").write_text(
        json.dumps({"cabecera-delatora": "User-Agent"}), encoding="utf-8"
    )
    codigo = cli.main(["check", str(EJERCICIO)])
    salida = capsys.readouterr().out
    assert codigo == 0
    assert "1/1 answers correct - 5/5 points" in salida
    assert "3/3 environment checks passed" in salida


def test_check_suspendido(monkeypatch, capsys, workdir):
    monkeypatch.chdir(workdir)
    runner = RecordingRunner({"grep": (0, "7\n", "")})
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    codigo = cli.main(["check", str(EJERCICIO)])
    salida = capsys.readouterr().out
    assert codigo == 1
    assert "FAIL" in salida
    assert "7 alerts" in salida


def test_answer_avisa_si_no_se_puede_escribir(workdir, monkeypatch, capsys):
    """Disco lleno: mensaje claro en vez de un traceback."""
    monkeypatch.chdir(workdir)

    def falla(*_args, **_kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(cli, "save_submitted", falla)
    assert cli.main(["answer", str(EJERCICIO), "cabecera-delatora", "User-Agent"]) == 1
    error = capsys.readouterr().err
    assert "cannot save the answer" in error
    assert "free disk space" in error


def test_answer_guarda_el_valor(workdir, monkeypatch, capsys):
    monkeypatch.chdir(workdir)
    assert cli.main(["answer", str(EJERCICIO), "cabecera-delatora", "User-Agent"]) == 0
    datos = json.loads((workdir / "answers" / "06-fuzz-evasion.json").read_text(encoding="utf-8"))
    assert datos == {"cabecera-delatora": "User-Agent"}


def test_answer_de_un_id_que_no_existe(workdir, monkeypatch, capsys):
    monkeypatch.chdir(workdir)
    assert cli.main(["answer", str(EJERCICIO), "inventada", "x"]) == 2
    assert "no answer 'inventada'" in capsys.readouterr().err


def test_down_con_perfil_inexistente_no_revienta(capsys):
    assert cli.main(["down", str(EJEMPLOS / "example.net.yaml"), "--profile", "noexiste"]) == 2
    salida = capsys.readouterr().err
    assert "does not exist" in salida
    assert "Available" in salida


def test_down_dry_run_lista_las_instancias(capsys):
    assert (
        cli.main(["down", str(EJEMPLOS / "example.net.yaml"), "--profile", "mini", "--dry-run"])
        == 0
    )
    salida = capsys.readouterr().out
    assert "incus stop fw" in salida
    assert "incus stop dmza" in salida
