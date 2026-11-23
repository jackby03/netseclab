"""`lab push` y `lab pull`: publicar y traer imágenes del bucket."""

from __future__ import annotations

import json
from pathlib import Path

from lab import cli
from lab.engine import RecordingRunner
from tynix.cache import FileCache


class _Exportador(RecordingRunner):
    """Simula `incus image export`: escribe el destino con la extensión añadida."""

    def run(self, argv, stdin=None):  # type: ignore[override]
        resultado = super().run(argv, stdin)
        if "image export" in " ".join(argv):
            # Incus no respeta el nombre exacto: `incus image export <alias> /tmp/x` deja
            # `/tmp/x.tar.gz`. El simulador hacía lo cómodo y escondía el fallo.
            Path(str(argv[-1]) + ".tar.gz").write_bytes(b"imagen exportada")
        return resultado


def _preparar(monkeypatch, tmp_path, runner=None):
    monkeypatch.chdir(tmp_path)
    runner = runner or _Exportador()
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    return runner


def test_push_publica_la_imagen_en_la_cache(tmp_path, monkeypatch, capsys):
    runner = _preparar(monkeypatch, tmp_path)
    bucket = tmp_path / "bucket"
    assert cli.main(["push", "lab-node-v1", "--to", str(bucket)]) == 0
    salida = capsys.readouterr().out
    assert "lab-node-v1" in salida
    assert "sha256:" in salida

    datos = json.loads((bucket / "index.json").read_text(encoding="utf-8"))
    assert datos["images"][0]["name"] == "lab-node-v1"
    assert (bucket / "lab-node-v1.tar.gz").exists()
    assert runner.contiene("image export lab-node-v1")


def test_pull_trae_verifica_e_importa(tmp_path, monkeypatch, capsys):
    bucket = tmp_path / "bucket"
    origen = tmp_path / "origen.tar.gz"
    origen.write_bytes(b"imagen buena")
    FileCache(bucket).add("lab-web-v1", origen)

    runner = _preparar(monkeypatch, tmp_path)
    assert cli.main(["pull", "lab-web-v1", "--from", str(bucket)]) == 0
    assert "sha256 verified" in capsys.readouterr().out
    assert runner.contiene("image import")
    assert runner.contiene("--alias lab-web-v1")


def test_pull_permite_otro_alias_local(tmp_path, monkeypatch):
    bucket = tmp_path / "bucket"
    origen = tmp_path / "origen.tar.gz"
    origen.write_bytes(b"imagen buena")
    FileCache(bucket).add("lab-web-v1", origen)

    runner = _preparar(monkeypatch, tmp_path)
    assert cli.main(["pull", "lab-web-v1", "--from", str(bucket), "--as", "mi-web"]) == 0
    assert runner.contiene("--alias mi-web")


def test_pull_de_algo_que_no_esta_lista_lo_disponible(tmp_path, monkeypatch, capsys):
    bucket = tmp_path / "bucket"
    origen = tmp_path / "origen.tar.gz"
    origen.write_bytes(b"x")
    FileCache(bucket).add("lab-web-v1", origen)

    _preparar(monkeypatch, tmp_path)
    assert cli.main(["pull", "no-existe", "--from", str(bucket)]) == 2
    error = capsys.readouterr().err
    assert "not in the cache" in error
    assert "lab-web-v1" in error


def test_pull_avisa_si_la_imagen_esta_corrupta(tmp_path, monkeypatch, capsys):
    bucket = tmp_path / "bucket"
    origen = tmp_path / "origen.tar.gz"
    origen.write_bytes(b"imagen buena")
    cache = FileCache(bucket)
    cache.add("lab-web-v1", origen)
    (bucket / "lab-web-v1.tar.gz").write_bytes(b"manipulada")

    runner = _preparar(monkeypatch, tmp_path)
    assert cli.main(["pull", "lab-web-v1", "--from", str(bucket)]) == 1
    assert "does not match its checksum" in capsys.readouterr().err
    assert not runner.contiene("image import")
