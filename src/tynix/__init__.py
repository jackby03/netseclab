"""tynix: entornos reproducibles para laboratorios de Incus.

Toma las ideas de Nix —declarativo, direccionado por contenido, verificable— sin
usar Nix ni NixOS. La base sigue siendo Debian y los nodos, contenedores: el
alumno ve un Linux normal y la reproducibilidad queda debajo.

Este paquete no importa nada de `lab` a propósito: se puede probar, documentar y
publicar por separado el día que crezca.
"""

__version__ = "0.0.1"

from .cache import Cache, CachedImage, FileCache, HttpCache, digest_file, open_cache, verify
from .errors import CacheError, InvalidLockError, TynixError
from .lock import Drift, Lock, read_lock, write_lock
from .manifest import Base, Environment, FileEntry, Package
from .store import ImageStore, garbage, image_name, missing, referenced

__all__ = [
    "Base",
    "Cache",
    "CacheError",
    "CachedImage",
    "Drift",
    "Environment",
    "FileCache",
    "FileEntry",
    "HttpCache",
    "ImageStore",
    "InvalidLockError",
    "Lock",
    "Package",
    "TynixError",
    "__version__",
    "digest_file",
    "garbage",
    "image_name",
    "missing",
    "open_cache",
    "read_lock",
    "referenced",
    "verify",
    "write_lock",
]
