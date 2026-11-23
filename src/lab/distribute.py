"""Cómo viaja un paquete de laboratorio: firma y descarga.

Un `.labpack` lleva el `sha256` de cada fichero, que detecta corrupción pero no suplantación: quien
manipule el paquete puede recalcular los hashes y el resultado cuadra. La firma es lo que ata el
paquete a una clave.

Se firma con `ssh-keygen -Y sign`, el mismo mecanismo con el que GitHub firma commits: OpenSSH 8.2 o
posterior, sin GPG, sin llavero y sin autoridad de certificación. La clave pública del profesor —un
fichero `.pub` de una línea— es lo único que hay que repartir, y la misma que ya usa para el SSH.
"""

from __future__ import annotations

import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import IO

from .tmp import carpeta_temporal

# El espacio de nombres de la firma. `ssh-keygen` lo mete dentro de la firma: una firma hecha para
# otro propósito (un commit, un tarball de releases) no vale como firma de un `.labpack`.
NAMESPACE = "netseclab"

# El principal que se espera en el fichero de firmantes. Es fijo para que el comando sea corto: al
# alumno le basta con decir qué clave pública acepta, no con mantener un `allowed_signers` a mano.
IDENTITY = "netseclab"

SIGNATURE_SUFFIX = ".sig"

_PREFIJOS_DE_CLAVE = ("ssh-", "ecdsa-", "sk-ssh-", "sk-ecdsa-")


class DistributeError(Exception):
    """Un paquete no se puede obtener o no se puede dar por bueno."""


class DownloadError(DistributeError):
    """El paquete no llegó: red, URL o permiso."""


class SignatureError(DistributeError):
    """La firma no está, no cuadra o no es de quien debería."""


def is_url(origen: str) -> bool:
    return origen.startswith(("http://", "https://"))


def remote_name(url: str) -> str:
    """Nombre con el que guardar el paquete descargado."""
    ruta = urllib.parse.urlparse(url).path
    if ruta.endswith("/"):
        return "labpack.labpack"
    return Path(ruta).name or "labpack.labpack"


def signature_path(labpack: Path) -> Path:
    """La firma vive al lado del paquete, con el sufijo `.sig`."""
    return labpack.with_name(labpack.name + SIGNATURE_SUFFIX)


def _ssh_keygen(
    *argumentos: str, entrada: IO[bytes] | None = None
) -> subprocess.CompletedProcess[str]:
    orden = ["ssh-keygen", *argumentos]
    try:
        return subprocess.run(orden, capture_output=True, text=True, stdin=entrada, check=False)
    except FileNotFoundError as exc:  # pragma: no cover - depende de la máquina
        raise SignatureError(
            "ssh-keygen is not installed: signed labpacks need OpenSSH 8.2 or newer"
        ) from exc


def sign(labpack: Path, key: Path) -> Path:
    """Firma el paquete con `key` y devuelve la ruta de la firma."""
    if not labpack.is_file():
        raise SignatureError(f"{labpack} does not exist")
    if not key.exists():
        raise SignatureError(f"signing key {key} does not exist")

    firma = signature_path(labpack)
    firma.unlink(missing_ok=True)
    resultado = _ssh_keygen("-Y", "sign", "-f", str(key), "-n", NAMESPACE, str(labpack))
    if resultado.returncode != 0 or not firma.is_file():
        detalle = (resultado.stderr or resultado.stdout).strip() or "ssh-keygen failed"
        raise SignatureError(f"cannot sign {labpack}: {detalle}")
    return firma


def _clave_publica(ruta: Path) -> str:
    if not ruta.is_file():
        raise SignatureError(f"public key {ruta} does not exist")
    for linea in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
        limpia = linea.strip()
        if not limpia or limpia.startswith("#"):
            continue
        if limpia.startswith(_PREFIJOS_DE_CLAVE):
            return limpia
        break
    raise SignatureError(f"{ruta} is not a public key: pass the .pub file, not the private key")


def verify(
    labpack: Path,
    signers: Sequence[Path],
    *,
    signature: Path | None = None,
) -> str:
    """Comprueba que la firma la hizo alguna de las claves dadas.

    Devuelve la línea de `ssh-keygen` con la huella de la clave que firmó, que es lo que se le
    enseña al alumno: «Good "netseclab" signature ... key SHA256:…».
    """
    firma = signature or signature_path(labpack)
    if not labpack.is_file():
        raise SignatureError(f"{labpack} does not exist")
    if not firma.is_file():
        raise SignatureError(
            f"{labpack} is not signed (missing {firma.name}): "
            "ask the author for the .sig or drop --signer"
        )
    if not signers:
        raise SignatureError("--signer needs at least one public key")

    claves = [_clave_publica(ruta) for ruta in signers]
    carpeta = carpeta_temporal()
    try:
        firmantes = carpeta / "allowed_signers"
        firmantes.write_text(
            "".join(f'{IDENTITY} namespaces="{NAMESPACE}" {clave}\n' for clave in claves),
            encoding="utf-8",
            newline="\n",
        )
        with labpack.open("rb") as datos:
            resultado = _ssh_keygen(
                "-Y",
                "verify",
                "-f",
                str(firmantes),
                "-I",
                IDENTITY,
                "-n",
                NAMESPACE,
                "-s",
                str(firma),
                entrada=datos,
            )
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)

    if resultado.returncode != 0:
        detalle = (resultado.stderr or resultado.stdout).strip() or "signature does not match"
        raise SignatureError(f"{labpack} is not signed by the expected key: {detalle}")
    salida = resultado.stdout.strip().splitlines()
    return salida[0] if salida else "signature verified"


def download(url: str, dest: Path) -> Path:
    """Trae el paquete de una URL. La integridad se comprueba después, con el manifiesto."""
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with (
            urllib.request.urlopen(url, timeout=60) as respuesta,  # noqa: S310
            dest.open("wb") as salida,
        ):
            shutil.copyfileobj(respuesta, salida)
    except (urllib.error.URLError, OSError) as exc:
        raise DownloadError(f"cannot download {url}: {exc}") from exc
    return dest
