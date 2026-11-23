"""Respuestas estrictas: un valor concreto, no una frase.

El alumno extrae un dato del laboratorio —una IP, un usuario, una contraseña, un
identificador— y lo entrega tal cual. Se guarda el hash del valor esperado, no el
valor, para que la copia que recibe el alumno no contenga la respuesta.

La comparación es intencionadamente literal: no se interpretan sinónimos ni se
busca una palabra dentro de un texto. Si un dato admite variantes legítimas, el
profesor las declara con `accepts`; el programa no las adivina.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# Un espacio cualquiera cuenta igual, y las tildes de la pregunta no afectan al
# valor. No se normalizan acentos del valor: una contraseña con tilde es otra.
_ESPACIOS = re.compile(r"\s+")


def normalize(texto: str) -> str:
    """Deja el valor comparable: sin espacios sobrantes, comillas ni mayúsculas."""
    limpio = texto.strip().strip("\"'`").strip()
    limpio = _ESPACIOS.sub(" ", limpio)
    return limpio.casefold()


def digest(texto: str) -> str:
    """sha256 del valor normalizado. Es lo único que necesita la copia del alumno."""
    return hashlib.sha256(normalize(texto).encode("utf-8")).hexdigest()


@dataclass
class Answer:
    id: str
    question: str
    points: int = 0
    kind: str = "fact"
    hashes: list[str] = field(default_factory=list)
    where: str = ""
    message: str = ""
    #: Valor en claro. Solo aparece en la copia del profesor: si está presente,
    #: la copia del alumno no está limpia y hay que hashearla antes de distribuir.
    clear: str = ""

    def accepts(self, texto: str) -> bool:
        return digest(texto) in self.hashes

    def describe(self) -> str:
        return self.question


def store(exercise_id: str, base: Path | None = None) -> Path:
    """Fichero donde se guardan las respuestas del alumno."""
    return (base or Path.cwd()) / "answers" / f"{exercise_id}.json"


def read_submitted(exercise_id: str, base: Path | None = None) -> dict[str, str]:
    ruta = store(exercise_id, base)
    if not ruta.exists():
        return {}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(datos, dict):
        return {}
    return {str(k): str(v) for k, v in datos.items()}


def save_submitted(exercise_id: str, answer_id: str, value: str, base: Path | None = None) -> Path:
    ruta = store(exercise_id, base)
    datos = read_submitted(exercise_id, base)
    datos[answer_id] = value
    ruta.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(datos, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ruta.write_text(texto, encoding="utf-8", newline="\n")
    return ruta
