"""tynix: entornos reproducibles para laboratorios de Incus.

Toma las ideas de Nix —declarativo, direccionado por contenido, verificable— sin
usar Nix ni NixOS. La base sigue siendo Debian y los nodos, contenedores: el
alumno ve un Linux normal y la reproducibilidad queda debajo.

Este paquete no importa nada de `lab` a propósito: se puede probar, documentar y
publicar por separado el día que crezca.
"""

__version__ = "0.0.1"

from .errors import InvalidLockError, TynixError
from .lock import Drift, Lock, read_lock, write_lock
from .manifest import Base, Environment, FileEntry, Package

__all__ = [
    "Base",
    "Drift",
    "Environment",
    "FileEntry",
    "InvalidLockError",
    "Lock",
    "Package",
    "TynixError",
    "__version__",
    "read_lock",
    "write_lock",
]
