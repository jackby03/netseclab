"""`.labpack`: empaquetar, verificar y extraer laboratorios."""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

import pytest

from lab import cli
from lab.errors import LabErrors
from lab.labpack import FORMAT, MANIFEST, pack, read_manifest, unpack, verify


def _arbol(tmp_path: Path) -> tuple[Path, Path]:
    (tmp_path / "lab" / "examples").mkdir(parents=True)
    (tmp_path / "lab" / "exercises").mkdir(parents=True)
    topo = tmp_path / "lab" / "examples" / "ejemplo.yaml"
    topo.write_text("version: 1\nname: ejemplo\n", encoding="utf-8", newline="\n")
    ejercicio = tmp_path / "lab" / "exercises" / "01.yaml"
    ejercicio.write_text("id: 01\n", encoding="utf-8", newline="\n")
    return topo, ejercicio


def test_empaquetar_genera_manifiesto_con_hashes(tmp_path):
    topo, _ = _arbol(tmp_path)
    salida = pack([topo], tmp_path / "p.labpack", name="ejemplo", root=tmp_path)
    manifiesto = read_manifest(salida)
    assert manifiesto["format"] == FORMAT
    assert manifiesto["name"] == "ejemplo"
    assert manifiesto["files"][0]["path"] == "lab/examples/ejemplo.yaml"
    assert len(manifiesto["files"][0]["sha256"]) == 64


def test_empaquetar_y_desempaquetar_da_lo_mismo(tmp_path):
    topo, ejercicio = _arbol(tmp_path)
    salida = pack([topo, ejercicio], tmp_path / "p.labpack", name="ejemplo", root=tmp_path)
    destino = tmp_path / "destino"
    extraidos = unpack(salida, destino)
    assert len(extraidos) == 2
    assert (destino / "lab" / "examples" / "ejemplo.yaml").read_text(encoding="utf-8") == (
        "version: 1\nname: ejemplo\n"
    )


def test_un_paquete_manipulado_no_se_extrae(tmp_path):
    topo, _ = _arbol(tmp_path)
    salida = pack([topo], tmp_path / "p.labpack", name="ejemplo", root=tmp_path)

    # se reescribe el blob con otro contenido, sin tocar el manifiesto
    otro = tmp_path / "otro.labpack"
    with tarfile.open(salida, "r:gz") as origen, tarfile.open(otro, "w:gz") as destino:
        for miembro in origen.getmembers():
            datos = origen.extractfile(miembro).read() if miembro.isfile() else b""
            if miembro.name.endswith(".yaml"):
                datos = b"version: 999\n"
            info = tarfile.TarInfo(miembro.name)
            info.size = len(datos)
            destino.addfile(info, io.BytesIO(datos))

    with pytest.raises(LabErrors, match="checksum mismatch"):
        verify(otro)
    with pytest.raises(LabErrors, match="checksum mismatch"):
        unpack(otro, tmp_path / "destino")


def test_un_paquete_que_intenta_escribir_fuera(tmp_path):
    malicioso = tmp_path / "malo.labpack"
    contenido = b"fuera"
    manifiesto = {
        "format": FORMAT,
        "version": 1,
        "name": "malo",
        "files": [{"path": "../evil.txt", "sha256": "0" * 64, "size": len(contenido)}],
    }
    with tarfile.open(malicioso, "w:gz") as tar:
        datos = (json.dumps(manifiesto) + "\n").encode("utf-8")
        info = tarfile.TarInfo(MANIFEST)
        info.size = len(datos)
        tar.addfile(info, io.BytesIO(datos))
        info = tarfile.TarInfo("../evil.txt")
        info.size = len(contenido)
        tar.addfile(info, io.BytesIO(contenido))

    # el checksum no cuadra (0*64): la verificación ya lo rechaza
    with pytest.raises(LabErrors):
        unpack(malicioso, tmp_path / "destino")
    assert not (tmp_path / "evil.txt").exists()


def test_un_fichero_que_falta_es_un_error(tmp_path):
    with pytest.raises(LabErrors, match="does not exist"):
        pack([tmp_path / "no-hay.yaml"], tmp_path / "p.labpack", name="x", root=tmp_path)


def test_lo_que_no_es_un_labpack_falla(tmp_path):
    basura = tmp_path / "basura.labpack"
    basura.write_bytes(b"esto no es un tar")
    with pytest.raises(LabErrors, match="not a valid labpack"):
        read_manifest(basura)


def test_cli_pack_y_unpack_dan_la_vuelta(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    topo, ejercicio = _arbol(tmp_path)
    salida = tmp_path / "ejemplo.labpack"
    assert (
        cli.main(
            [
                "pack",
                str(topo),
                "--out",
                str(salida),
                "--exercise",
                str(ejercicio),
                "--name",
                "ejemplo",
            ]
        )
        == 0
    )
    assert "packed" in capsys.readouterr().out

    destino = tmp_path / "extraido"
    assert cli.main(["unpack", str(salida), "--to", str(destino)]) == 0
    assert "files extracted" in capsys.readouterr().out
    assert (destino / "lab" / "exercises" / "01.yaml").exists()
