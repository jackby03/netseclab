"""Carga de ejercicios autocorregibles.

La pregunta es texto libre: puede estar en cualquier idioma y decir lo que el
profesor quiera. Lo que se valida es la respuesta, que tiene que ser un valor
concreto comparable por hash.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .answers import Answer, digest
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
    answers: list[Answer] = field(default_factory=list)
    report: list[str] = field(default_factory=list)
    solution: str = ""

    @property
    def points(self) -> int:
        return sum(a.points for a in self.answers)

    @property
    def reveals_answers(self) -> bool:
        """¿La copia del alumno lleva los valores en claro?"""
        return any(a.clear for a in self.answers)


def _cargar_answers(bruto: Any, sc: Scope) -> list[Answer]:
    if bruto is None:
        return []
    if not isinstance(bruto, list):
        sc.add("answers", "expected a list")
        return []
    salida: list[Answer] = []
    vistos: set[str] = set()
    for idx, item in enumerate(bruto):
        where = f"answers[{idx}]"
        if not isinstance(item, dict):
            sc.add(where, "expected a map")
            continue
        ident = str(item.get("id", "") or "")
        if not ident:
            sc.add(f"{where}.id", "required")
        elif ident in vistos:
            sc.add(f"{where}.id", f"duplicated: {ident!r}")
        vistos.add(ident)
        pregunta = str(item.get("question", "") or "").strip()
        if not pregunta:
            sc.add(f"{where}.question", "required")
        puntos = item.get("points", 0)
        try:
            puntos = int(puntos)
        except (TypeError, ValueError):
            sc.add(f"{where}.points", "expected an integer")
            puntos = 0
        if puntos < 0:
            sc.add(f"{where}.points", "must be zero or more")
        tipo = str(item.get("kind", "fact") or "fact")
        if tipo not in ("fact", "flag"):
            sc.add(f"{where}.kind", "must be 'fact' or 'flag'")

        hashes: list[str] = []
        claro = item.get("value")
        if claro is not None:
            claro = str(claro)
            hashes.append(digest(claro))
        aceptados = item.get("accepts")
        if aceptados is not None:
            if not isinstance(aceptados, list):
                sc.add(f"{where}.accepts", "expected a list of values")
            else:
                hashes.extend(digest(str(v)) for v in aceptados)
        hashs = item.get("hash")
        if hashs is not None:
            if isinstance(hashs, list):
                hashes.extend(str(h) for h in hashs)
            else:
                hashes.append(str(hashs))
        if not hashes:
            sc.add(f"{where}", "needs 'hash', 'value' or 'accepts'")
        salida.append(
            Answer(
                id=ident,
                question=pregunta,
                points=puntos,
                kind=tipo,
                hashes=list(dict.fromkeys(hashes)),
                where=str(item.get("where", "") or ""),
                message=str(item.get("message", "") or ""),
                clear="" if claro is None else str(claro),
            )
        )
    return salida


def load(path: str | Path) -> Exercise:
    path = Path(path)
    if not path.exists():
        raise LabErrors([Issue(str(path), "the exercise does not exist")])
    try:
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise LabErrors([Issue(str(path), f"invalid YAML: {exc}")]) from exc
    if not isinstance(raw, dict):
        raise LabErrors([Issue(str(path), "the document must be a map at the root")])

    sc = Scope()
    ident = str(raw.get("id", ""))
    if not ident:
        sc.add("id", "required")
    lab_rel = raw.get("lab")
    if not lab_rel:
        sc.add("lab", "required: path to the exercise topology")
        lab_path = path
    else:
        lab_path = (path.parent / str(lab_rel)).resolve()
        if not lab_path.exists():
            sc.add("lab", f"{lab_path} does not exist")

    checks_raw = raw.get("checks") or []
    if not isinstance(checks_raw, list):
        sc.add("checks", "expected a list")
        checks_raw = []
    checks: list[Check] = []
    for idx, item in enumerate(checks_raw):
        if not isinstance(item, dict):
            sc.add(f"checks[{idx}]", "expected a map with 'assert'")
            continue
        try:
            checks.append(parse_check(item, f"checks[{idx}]"))
        except LabErrors as exc:
            sc.issues.extend(exc.issues)

    answers = _cargar_answers(raw.get("answers"), sc)

    if not checks and not answers:
        sc.add("checks", "an exercise needs at least one check or answer")

    report = raw.get("report") or []
    if not isinstance(report, list):
        sc.add("report", "expected a list of questions")
        report = []

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
        answers=answers,
        report=[str(r) for r in report],
        solution=str(raw.get("solution", "") or "").strip(),
    )
