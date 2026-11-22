"""Catálogo de imágenes y toolsets."""

from __future__ import annotations

from pathlib import Path

import yaml

from .errors import Issue, LabErrors


def default_root() -> Path:
    """Raíz del repositorio (donde vive `lab/`)."""
    return Path(__file__).resolve().parents[2]


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise LabErrors([Issue(str(path), f"YAML no válido: {exc}")]) from exc
    if not isinstance(data, dict):
        raise LabErrors([Issue(str(path), "se esperaba un mapa en la raíz")])
    return data


def load_images(root: Path | None = None) -> dict[str, str]:
    root = root or default_root()
    data = _load(root / "lab" / "images.yaml")
    imagenes = data.get("images") or {}
    return {str(k): str(v) for k, v in imagenes.items()}


def load_toolsets(root: Path | None = None) -> dict[str, list[str]]:
    root = root or default_root()
    data = _load(root / "lab" / "toolsets.yaml")
    out: dict[str, list[str]] = {}
    for nombre, spec in (data.get("toolsets") or {}).items():
        if isinstance(spec, dict):
            out[str(nombre)] = [str(p) for p in spec.get("packages") or []]
        elif isinstance(spec, list):
            out[str(nombre)] = [str(p) for p in spec]
    return out


def resolve_image(alias: str, images: dict[str, str], where: str = "image") -> str:
    """Traduce un alias del catálogo a la referencia que entiende Incus."""
    if alias in images:
        return images[alias]
    if ":" in alias or "/" in alias:
        return alias
    raise LabErrors(
        [
            Issue(
                where,
                f"la imagen {alias!r} no está en el catálogo. Añádela a lab/images.yaml "
                f"o usa una referencia completa (images:debian/13).",
            )
        ]
    )
