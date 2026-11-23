"""Imágenes propias: recetas que se construyen con Incus y se publican en el catálogo local.

Una receta no es más que un nodo de un solo uso: se arranca, se le instalan paquetes y ficheros, se
ejecuta su `startup` y se publica con un alias `lab/<nombre>:<versión>`. Así un escenario puede
pedir `image: soc-lite` y arrancar en segundos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .catalog import load_images, resolve_image
from .errors import Issue, LabErrors, Scope
from .plan import PERFIL_NODOS, Step

CLAVES = {"name", "base", "version", "description", "packages", "assets", "startup", "size"}
SALIDA = "lab-build"


@dataclass
class ImageRecipe:
    name: str
    base: str
    path: Path
    version: str = "1"
    description: str = ""
    packages: list[str] = field(default_factory=list)
    assets: list[tuple[str, str]] = field(default_factory=list)
    startup: str = ""
    size: str = ""

    @property
    def referencia(self) -> str:
        return f"lab/{self.name}:{self.version}"

    @property
    def instancia(self) -> str:
        return f"{SALIDA}-{self.name}"


def load_recipe(path: str | Path) -> ImageRecipe:
    path = Path(path)
    if not path.exists():
        raise LabErrors([Issue(str(path), "the recipe does not exist")])
    try:
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise LabErrors([Issue(str(path), f"invalid YAML: {exc}")]) from exc
    if not isinstance(raw, dict):
        raise LabErrors([Issue(str(path), "the recipe must be a map at the root")])

    sc = Scope()
    for clave in raw:
        if clave not in CLAVES:
            sc.add(f"{clave}", f"unknown key in recipe; allowed: {', '.join(sorted(CLAVES))}")

    nombre = str(raw.get("name", ""))
    if not nombre:
        sc.add("name", "required")
    base = str(raw.get("base", "debian13"))
    if not base:
        sc.add("base", "required")

    assets: list[tuple[str, str]] = []
    for idx, item in enumerate(raw.get("assets") or []):
        if not isinstance(item, dict) or "src" not in item or "dst" not in item:
            sc.add(f"assets[{idx}]", "each asset needs src and dst")
            continue
        assets.append((str(item["src"]), str(item["dst"])))

    sc.raise_if_any()

    return ImageRecipe(
        name=nombre,
        base=base,
        path=path,
        version=str(raw.get("version", "1")),
        description=str(raw.get("description", "") or ""),
        packages=[str(p) for p in raw.get("packages") or []],
        assets=assets,
        startup=str(raw.get("startup", "") or ""),
        size=str(raw.get("size", "") or ""),
    )


def build_plan(recipe: ImageRecipe, root: Path | None = None) -> list[Step]:
    imagenes = load_images(root)
    base = resolve_image(recipe.base, imagenes, where=f"{recipe.name}.base")
    inst = recipe.instancia
    pasos: list[Step] = [
        Step("limpiar", argv=["incus", "delete", inst, "--force"],
             note=f"in case a half-finished build of {recipe.name} is left"),
        Step("crear", argv=["incus", "launch", base, inst, "--profile", PERFIL_NODOS],
             note=f"{recipe.name} from {base}"),
    ]

    if recipe.size:
        pasos.append(
            Step("crear", argv=["incus", "config", "device", "override", inst, "root", f"size={recipe.size}"],
                 note=f"disk of {recipe.size}")
        )

    if recipe.packages:
        lista = " ".join(recipe.packages)
        pasos.append(
            Step("paquetes", node=inst,
                 argv=["sh", "-c", ("apt-get update -qq && "
                       f"DEBIAN_FRONTEND=noninteractive apt-get install -y -qq {lista}")],
                 note=f"{len(recipe.packages)} packages")
        )

    carpeta = recipe.path.parent
    for src, dst in recipe.assets:
        origen = (carpeta / src).resolve()
        if origen.is_dir():
            pasos.append(Step("ficheros", kind="tar", node=inst, path=dst, argv=[str(origen)],
                              note=f"{src}/ -> {dst}"))
        elif origen.is_file():
            pasos.append(Step("ficheros", kind="push", node=inst, path=dst,
                              content=origen.read_text(encoding="utf-8")))
        else:
            raise FileNotFoundError(f"recipe {recipe.name} points to {origen}, which does not exist")

    if recipe.startup.strip():
        pasos.append(
            Step("arranque", node=inst, argv=["sh", "-c", recipe.startup], note="recipe startup")
        )

    pasos += [
        Step("publicar", argv=["incus", "stop", inst], note="an image is published with the instance stopped"),
        Step("publicar", argv=["incus", "publish", inst, "--alias", recipe.referencia],
             note=f"alias {recipe.referencia}"),
        Step("limpiar", argv=["incus", "delete", inst, "--force"], note="delete the temporary instance"),
    ]
    return pasos


def listar_imagenes(runner) -> list[str]:
    res = runner.run(["incus", "image", "list", "--format", "csv", "-c", "aliases"])
    if not res.ok:
        return []
    return sorted(
        linea.strip() for linea in res.out.splitlines() if linea.strip().startswith("lab/")
    )
