"""Paso de un plan: un comando, una copia o un tar."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field


@dataclass
class Step:
    phase: str
    kind: str = "cmd"  # cmd | push | tar
    argv: list[str] = field(default_factory=list)
    node: str | None = None
    note: str = ""
    path: str = ""
    content: str = ""
    mode: str = "0644"

    def command(self) -> str:
        return " ".join(shlex.quote(a) for a in self.exec_argv())

    def exec_argv(self) -> list[str]:
        """Lista de argumentos lista para ejecutar sin pasar por un shell."""
        if self.kind == "push":
            raise ValueError("a push is not a command")
        if self.kind == "tar":
            origen = shlex.quote(self.argv[0])
            destino = shlex.quote(self.path)
            nodo = shlex.quote(self.node or "")
            return [
                "sh",
                "-c",
                f"tar -C {origen} -cf - . | incus exec {nodo} -- tar -C {destino} -xf -",
            ]
        if self.node:
            return ["incus", "exec", self.node, "--", *self.argv]
        return list(self.argv)

    def as_dict(self) -> dict:
        return {
            "phase": self.phase,
            "kind": self.kind,
            "node": self.node,
            "command": self.command() if self.kind != "push" else None,
            "path": self.path or None,
            "note": self.note or None,
        }
