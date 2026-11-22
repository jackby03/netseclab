import shutil
import sys
import uuid
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))


@pytest.fixture
def workdir():
    """Directorio temporal propio.

    No se usa `tmp_path` porque el sandbox de este entorno no siempre permite listar los
    directorios temporales que crea pytest.
    """
    base = RAIZ / "build" / "tests" / uuid.uuid4().hex[:8]
    base.mkdir(parents=True)
    try:
        yield base
    finally:
        shutil.rmtree(base, ignore_errors=True)
