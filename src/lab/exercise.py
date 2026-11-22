"""Carga de ejercicios autocorregibles."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .checks import Check, parse_check
from .errors import Issue, LabErrors, Scope


@dataclass
class Exercise:
    id: str
    title: str
    lab: Path
    path: Path
    profile: str | None = None
    initial: str = "initial"
    difficulty: str = ""
    duration: str = ""
    brief: str = ""
    tasks: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    solution: str = ""

    @property
    def answer_file(self) -> Path:
        return Path.cwd() / "answers" / f"{self.id}.txt"


def load(path: str | Path) -> Exercise:
    path = Path(path)
    if not path.exists():
        raise LabErrors([Issue(str(path), "el ejercicio no existe")])
    try:
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise LabErrors([Issue(str(path), f"YAML no válido: {exc}")]) from exc
    if not isinstance(raw, dict):
        raise LabErrors([Issue(str(path), "el documento debe ser un mapa en la raíz")])

    sc = Scope()
    ident = str(raw.get("id", ""))
    if not ident:
        sc.add("id", "obligatorio")
    lab_rel = raw.get("lab")
    if not lab_rel:
        sc.add("lab", "obligatorio: ruta a la topología del ejercicio")
        lab_path = path
    else:
        lab_path = (path.parent / str(lab_rel)).resolve()
        if not lab_path.exists():
            sc.add("lab", f"no existe {lab_path}")

    checks_raw = raw.get("checks") or []
    if not isinstance(checks_raw, list) or not checks_raw:
        sc.add("checks", "un ejercicio necesita al menos una comprobación")
        checks_raw = []
    checks: list[Check] = []
    for idx, item in enumerate(checks_raw):
        if not isinstance(item, dict):
            sc.add(f"checks[{idx}]", "se esperaba un mapa con 'assert'")
            continue
        try:
            checks.append(parse_check(item, f"checks[{idx}]"))
        except LabErrors as exc:
            sc.issues.extend(exc.issues)

    sc.raise_if_any()

    return Exercise(
        id=ident,
        title=str(raw.get("title", ident)),
        lab=lab_path,
        path=path,
        profile=raw.get("profile"),
        initial=str(raw.get("initial", "initial")),
        difficulty=str(raw.get("difficulty", "")),
        duration=str(raw.get("duration", "")),
        brief=str(raw.get("brief", "") or "").strip(),
        tasks=[str(t) for t in raw.get("tasks") or []],
        hints=[str(h) for h in raw.get("hints") or []],
        checks=checks,
        solution=str(raw.get("solution", "") or "").strip(),
    )


def read_answer(exercise: Exercise) -> str:
    if exercise.answer_file.exists():
        return exercise.answer_file.read_text(encoding="utf-8")
    return ""


def write_answer(exercise: Exercise, texto: str) -> Path:
    exercise.answer_file.parent.mkdir(parents=True, exist_ok=True)
    exercise.answer_file.write_text(texto, encoding="utf-8")
    return exercise.answer_file
