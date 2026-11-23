"""Distribución de `.labpack`: firma con OpenSSH y descarga por URL."""

from __future__ import annotations

import functools
import http.server
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from lab import cli
from lab.distribute import (
    DownloadError,
    SignatureError,
    download,
    remote_name,
    sign,
    signature_path,
    verify,
)
from lab.labpack import pack

SSH_KEYGEN = shutil.which("ssh-keygen")
sin_ssh = pytest.mark.skipif(SSH_KEYGEN is None, reason="hace falta ssh-keygen (OpenSSH 8.2+)")


def _clave(destino: Path, nombre: str = "id_ed25519") -> tuple[Path, Path]:
    """Genera un par de claves sin contraseña. Devuelve (privada, pública)."""
    privada = destino / nombre
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "netseclab-test", "-f", str(privada)],
        check=True,
        capture_output=True,
    )
    return privada, privada.with_name(privada.name + ".pub")


def _paquete(tmp_path: Path, nombre: str = "ejemplo.labpack") -> Path:
    topo = tmp_path / "lab.yaml"
    topo.write_text("version: 1\nname: ejemplo\n", encoding="utf-8", newline="\n")
    return pack([topo], tmp_path / nombre, name="ejemplo", root=tmp_path)


@sin_ssh
def test_firmar_y_verificar(tmp_path):
    privada, publica = _clave(tmp_path)
    paquete = _paquete(tmp_path)

    firma = sign(paquete, privada)
    assert firma == signature_path(paquete)
    assert firma.is_file()

    mensaje = verify(paquete, [publica])
    assert mensaje.startswith("Good")
    assert "SHA256:" in mensaje


@sin_ssh
def test_un_paquete_tocado_despues_de_firmar_no_cuadra(tmp_path):
    privada, publica = _clave(tmp_path)
    paquete = _paquete(tmp_path)
    sign(paquete, privada)

    paquete.write_bytes(paquete.read_bytes() + b"\x00")

    with pytest.raises(SignatureError, match="not signed by the expected key"):
        verify(paquete, [publica])


@sin_ssh
def test_firmado_por_otra_clave_no_vale(tmp_path):
    privada, _ = _clave(tmp_path)
    _, ajena = _clave(tmp_path, "otra")
    paquete = _paquete(tmp_path)
    sign(paquete, privada)

    with pytest.raises(SignatureError, match="not signed by the expected key"):
        verify(paquete, [ajena])


@sin_ssh
def test_sin_firma_el_paquete_no_se_da_por_bueno(tmp_path):
    _, publica = _clave(tmp_path)
    paquete = _paquete(tmp_path)

    with pytest.raises(SignatureError, match="is not signed"):
        verify(paquete, [publica])


@sin_ssh
def test_la_clave_privada_no_sirve_para_verificar(tmp_path):
    privada, _ = _clave(tmp_path)
    paquete = _paquete(tmp_path)
    sign(paquete, privada)

    with pytest.raises(SignatureError, match="not a public key"):
        verify(paquete, [privada])


def test_firmar_sin_clave_falla_con_mensaje(tmp_path):
    paquete = _paquete(tmp_path)
    with pytest.raises(SignatureError, match="does not exist"):
        sign(paquete, tmp_path / "no-hay-clave")


def test_verificar_un_paquete_que_no_existe(tmp_path):
    with pytest.raises(SignatureError, match="does not exist"):
        verify(tmp_path / "no-hay.labpack", [tmp_path / "clave.pub"])


def test_descargar_y_nombrar(tmp_path):
    origen = _paquete(tmp_path)
    destino = tmp_path / "traido" / "ejemplo.labpack"
    assert download(origen.as_uri(), destino) == destino
    assert destino.read_bytes() == origen.read_bytes()

    assert remote_name("https://bucket.universidad.edu/labs/edr.labpack") == "edr.labpack"
    assert remote_name("https://bucket.universidad.edu/labs/") == "labpack.labpack"


def test_una_url_que_no_existe_es_un_error_claro(tmp_path):
    with pytest.raises(DownloadError, match="cannot download"):
        download((tmp_path / "no-hay.labpack").as_uri(), tmp_path / "x.labpack")


class _Silencioso(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def servidor(tmp_path):
    """Sirve `tmp_path` por HTTP en un puerto libre: simula el bucket del curso."""
    handler = functools.partial(_Silencioso, directory=str(tmp_path))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    hilo = threading.Thread(target=httpd.serve_forever, daemon=True)
    hilo.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        hilo.join(timeout=5)


@sin_ssh
def test_cli_pack_firma_y_unpack_verifica(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    privada, publica = _clave(tmp_path)
    topo = tmp_path / "lab.yaml"
    topo.write_text("version: 1\nname: ejemplo\n", encoding="utf-8", newline="\n")
    paquete = tmp_path / "ejemplo.labpack"

    assert cli.main(["pack", str(topo), "--out", str(paquete), "--sign", str(privada)]) == 0
    salida = capsys.readouterr().out
    assert "signed:" in salida
    assert (tmp_path / "ejemplo.labpack.sig").is_file()

    destino = tmp_path / "extraido"
    assert cli.main(["unpack", str(paquete), "--to", str(destino), "--signer", str(publica)]) == 0
    salida = capsys.readouterr().out
    assert "signature ok:" in salida
    assert "files extracted" in salida
    assert (destino / "lab.yaml").is_file()


@sin_ssh
def test_cli_unpack_rechaza_una_firma_ajena(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    privada, _ = _clave(tmp_path)
    _, ajena = _clave(tmp_path, "otra")
    topo = tmp_path / "lab.yaml"
    topo.write_text("version: 1\nname: ejemplo\n", encoding="utf-8", newline="\n")
    paquete = tmp_path / "ejemplo.labpack"
    assert cli.main(["pack", str(topo), "--out", str(paquete), "--sign", str(privada)]) == 0
    capsys.readouterr()

    destino = tmp_path / "extraido"
    assert cli.main(["unpack", str(paquete), "--to", str(destino), "--signer", str(ajena)]) == 2
    assert "not signed by the expected key" in capsys.readouterr().err
    assert not destino.exists()


def test_cli_unpack_pide_signer_para_usar_signature(tmp_path, capsys):
    assert cli.main(["unpack", "x.labpack", "--to", str(tmp_path / "d"), "--signature", "s"]) == 2
    assert "--signer" in capsys.readouterr().err


@sin_ssh
def test_cli_unpack_desde_una_url(tmp_path, monkeypatch, capsys, servidor):
    monkeypatch.chdir(tmp_path)
    privada, _ = _clave(tmp_path)
    topo = tmp_path / "lab.yaml"
    topo.write_text("version: 1\nname: ejemplo\n", encoding="utf-8", newline="\n")
    paquete = tmp_path / "ejemplo.labpack"
    assert cli.main(["pack", str(topo), "--out", str(paquete), "--sign", str(privada)]) == 0
    capsys.readouterr()

    destino = tmp_path / "desde-url"
    assert (
        cli.main(
            [
                "unpack",
                f"{servidor}/ejemplo.labpack",
                "--to",
                str(destino),
                "--signer",
                f"{servidor}/id_ed25519.pub",
            ]
        )
        == 0
    )
    salida = capsys.readouterr().out
    assert "signature ok:" in salida
    assert (destino / "lab.yaml").is_file()


def test_cli_unpack_sin_firma_sigue_funcionando(tmp_path, monkeypatch, capsys):
    """Quien no pide firma se queda con la verificación de checksums de siempre."""
    monkeypatch.chdir(tmp_path)
    topo = tmp_path / "lab.yaml"
    topo.write_text("version: 1\nname: ejemplo\n", encoding="utf-8", newline="\n")
    paquete = tmp_path / "ejemplo.labpack"
    assert cli.main(["pack", str(topo), "--out", str(paquete)]) == 0
    capsys.readouterr()

    destino = tmp_path / "extraido"
    assert cli.main(["unpack", str(paquete), "--to", str(destino)]) == 0
    assert "signature ok" not in capsys.readouterr().out
