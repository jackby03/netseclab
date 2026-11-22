"""CLI del laboratorio.

Principio: el CLI no esconde la herramienta. Todo lo que hace se puede ver con `lab render`, y en
las prácticas se enseña el comando equivalente de Incus.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import __version__
from .catalog import load_images, load_toolsets
from .checks import run_check
from .engine import (
    Incus,
    RecordingRunner,
    Runner,
    SubprocessRunner,
    execute,
    restore_snapshot,
    take_snapshot,
)
from .engine.capture import plan_capture, run_capture
from .engine.incus import SNAPSHOT_INICIAL
from .errors import LabErrors
from .exercise import load as load_exercise
from .exercise import read_answer, write_answer
from .model import load
from .plan import Plan, build


# --------------------------------------------------------------------------- utilidades


def _cargar(ruta: str):
    try:
        return load(ruta)
    except LabErrors as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)


def _plan(args) -> Plan:
    topo = _cargar(args.file)
    try:
        return build(topo, profile=getattr(args, "profile", None))
    except KeyError:
        disponibles = ", ".join(sorted(topo.profiles)) or "(none)"
        print(
            f"error: profile {args.profile!r} does not exist in {args.file}. "
            f"Available: {disponibles}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    except LabErrors as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)


def _runner() -> Runner:
    return SubprocessRunner()


def _sin_incus() -> bool:
    if shutil.which("incus") is None:
        print(
            "error: the `incus` command was not found.\n"
            "  This command has to run inside the box (the VM with Incus).\n"
            "  To see what it would do, run: lab render <topology>",
            file=sys.stderr,
        )
        return True
    return False


def _tabla(plan: Plan) -> str:
    lineas = [
        f"lab: {plan.topology.name}   domain: {plan.topology.domain}"
        + (f"   profile: {plan.profile}" if plan.profile else ""),
        "",
        "NETWORKS",
        f"  {'name':<10} {'cidr':<16} {'type':<9} {'mode':<7} {'bridge':<14} gateway",
    ]
    for net in plan.used_networks():
        lineas.append(
            f"  {net.name:<10} {net.cidr:<16} {net.type:<9} {net.mode:<7} "
            f"{net.bridge:<14} {net.gateway or '-'}"
        )
    lineas += ["", "NODES", f"  {'name':<10} {'image':<22} interfaces"]
    for node in plan.nodes:
        bocas = ", ".join(f"{l.ifname}={l.ip}/{l.prefix}" for l in node.links)
        lineas.append(f"  {node.name:<10} {node.image:<22} {bocas}")
    lineas += ["", f"{len(plan.steps)} steps"]
    return "\n".join(lineas)


def _informe(resultados: list[tuple[str, bool, str]]) -> str:
    lineas = []
    for descripcion, ok, detalle in resultados:
        marca = "OK   " if ok else "FAIL"
        lineas.append(f"  [{marca}] {descripcion}")
        if detalle:
            lineas.append(f"          {detalle}")
    return "\n".join(lineas)


# --------------------------------------------------------------------------- comandos


def cmd_validate(args) -> int:
    from glob import glob

    rutas: list[str] = []
    for patron in args.files:
        if any(c in patron for c in "*?["):
            encontradas = sorted(glob(patron))
            if not encontradas:
                print(f"{patron}: no files match", file=sys.stderr)
                rutas.append(patron)
            rutas.extend(encontradas)
        else:
            rutas.append(patron)

    fallos = 0
    for ruta in rutas:
        try:
            import yaml

            datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8")) or {}
        except (OSError, Exception):  # el error real lo dará el cargador correspondiente
            datos = {}

        es_ejercicio = isinstance(datos, dict) and "checks" in datos and "lab" in datos
        try:
            if es_ejercicio:
                ejercicio = load_exercise(ruta)
                print(
                    f"{ruta}: OK - exercise {ejercicio.id} with "
                    f"{len(ejercicio.checks)} checks"
                )
                continue
            topo = load(ruta)
        except LabErrors as exc:
            print(f"{ruta}: NOT VALID", file=sys.stderr)
            print(str(exc), file=sys.stderr)
            fallos += 1
            continue
        print(
            f"{ruta}: OK - {len(topo.nodes)} nodes, {len(topo.networks)} networks, "
            f"{len(topo.policies)} policies"
        )
    return 0 if fallos == 0 else 1


def cmd_render(args) -> int:
    plan = _plan(args)
    if args.out:
        destino = Path(args.out)
        destino.mkdir(parents=True, exist_ok=True)
        escritos = plan.write_files(destino)
        (destino / "lab.sh").write_text(plan.shell(), encoding="utf-8")
        (destino / "plan.json").write_text(
            json.dumps(plan.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        if args.format == "table":
            print(_tabla(plan))
        print(
            f"wrote {len(escritos)} files to {destino} (plus lab.sh and plan.json)",
            file=sys.stderr,
        )
        return 0
    if args.format == "json":
        print(json.dumps(plan.as_dict(), indent=2, ensure_ascii=False))
    elif args.format == "table":
        print(_tabla(plan))
    else:
        print(plan.shell())
    return 0


def cmd_up(args) -> int:
    plan = _plan(args)
    print(_tabla(plan))
    print()

    if args.dry_run:
        for step in plan.steps:
            if step.kind != "push":
                print(f"-> {step.command()}")
        return 0

    if _sin_incus():
        return 3

    # Sin esto la pantalla se queda congelada durante un minuto y parece colgada.
    total = len(plan.steps)
    hechos = 0

    def progreso(step) -> None:
        nonlocal hechos
        hechos += 1
        etiqueta = step.note or step.phase
        print(f"  [{hechos:>2}/{total}] {etiqueta}", flush=True)

    print("running the plan (Ctrl-C to interrupt; run it again to continue):")
    outcome = execute(plan, _runner(), seguir=args.keep_going, on_step=progreso)
    print()
    print(outcome.resumen())
    for comando, error in outcome.fallos:
        print(f"  failed: {comando}", file=sys.stderr)
        if error:
            print(f"          {error}", file=sys.stderr)

    if outcome.ok and not args.no_snapshot:
        incus = Incus(_runner())
        fallos = take_snapshot(incus, [n.name for n in plan.nodes], SNAPSHOT_INICIAL)
        if fallos:
            print("warning: could not create the initial snapshot:", file=sys.stderr)
            for fallo in fallos:
                print(f"  {fallo}", file=sys.stderr)
        else:
            print(f"snapshot {SNAPSHOT_INICIAL!r} created: `lab reset` returns here")
    return 0 if outcome.ok else 1


def cmd_down(args) -> int:
    topo = _cargar(args.file)
    try:
        nombres = list(args.names) or [n.name for n in topo.resolve_profile(args.profile)]
    except KeyError:
        disponibles = ", ".join(sorted(topo.profiles)) or "(none)"
        print(
            f"error: profile {args.profile!r} does not exist in {args.file}. "
            f"Available: {disponibles}",
            file=sys.stderr,
        )
        return 2
    if args.dry_run:
        for nombre in nombres:
            print(f"-> incus stop {nombre}")
        return 0
    if _sin_incus():
        return 3
    incus = Incus(_runner())
    fallos = 0
    for nombre in nombres:
        res = incus._run("stop", nombre)
        print(f"{nombre}: {'stopped' if res.ok else (res.err.strip() or 'error')}")
        fallos += 0 if res.ok else 1
    return 0 if fallos == 0 else 1


def cmd_status(args) -> int:
    if _sin_incus():
        return 3
    incus = Incus(_runner())
    instancias = incus.listar()
    if not instancias:
        print("no instances")
        return 0
    print(f"{'name':<12} {'state':<12} {'type':<10} ipv4")
    for inst in instancias:
        print(f"{inst.name:<12} {inst.status:<12} {inst.type:<10} {', '.join(inst.ips) or '-'}")
    return 0


def cmd_console(args) -> int:
    if _sin_incus():
        return 3
    import os

    instancias = {i.name: i for i in Incus(_runner()).listar()}
    instancia = instancias.get(args.name)
    if instancia is None:
        print(f"error: node {args.name!r} does not exist", file=sys.stderr)
        return 1
    if instancia.status.lower() != "running":
        print(
            f"{args.name} is not running; showing its log instead. "
            "Bring the lab up to get an interactive console.",
            file=sys.stderr,
        )
        os.execvp("incus", ["incus", "console", "--show-log", args.name])
        return 0  # pragma: no cover

    print(f"Connecting to {args.name}. To leave: Ctrl-a, then q.", file=sys.stderr, flush=True)
    os.execvp("incus", ["incus", "console", args.name])
    return 0  # pragma: no cover


def cmd_snapshot(args) -> int:
    plan = _plan(args)
    if _sin_incus():
        return 3
    incus = Incus(_runner())
    fallos = take_snapshot(incus, [n.name for n in plan.nodes], args.name)
    if fallos:
        for fallo in fallos:
            print(f"  {fallo}", file=sys.stderr)
        return 1
    print(f"snapshot {args.name!r} created on {len(plan.nodes)} nodes")
    return 0


def cmd_reset(args) -> int:
    plan = _plan(args)
    if _sin_incus():
        return 3
    incus = Incus(_runner())
    fallos = restore_snapshot(incus, [n.name for n in plan.nodes], args.name)
    if fallos:
        for fallo in fallos:
            print(f"  {fallo}", file=sys.stderr)
        print(
            f"\nSnapshot {args.name!r} does not exist? Create it with `lab up` "
            f"(it takes {SNAPSHOT_INICIAL!r} at the end) or with `lab snapshot {args.file}`.",
            file=sys.stderr,
        )
        return 1
    print(f"lab restored to {args.name!r} on {len(plan.nodes)} nodes")
    return 0


def cmd_capture(args) -> int:
    topo = _cargar(args.file)
    if args.net not in topo.networks:
        print(
            f"error: network {args.net!r} does not exist. Available: "
            f"{', '.join(sorted(topo.networks))}",
            file=sys.stderr,
        )
        return 2
    salida = Path(args.out or f"capture/{args.net}.pcap")
    salida.parent.mkdir(parents=True, exist_ok=True)
    plan = plan_capture(topo, topo.networks[args.net], args.seconds, salida)
    if _sin_incus():
        return 3
    ok, detalle = run_capture(plan, _runner())
    if not ok:
        print(f"error: {detalle}", file=sys.stderr)
        return 1
    print(f"{detalle} -> {salida}")
    return 0


def cmd_check(args) -> int:
    try:
        ejercicio = load_exercise(args.file)
    except LabErrors as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        topo = load(ejercicio.lab)
    except LabErrors as exc:
        print(f"the exercise lab is not valid:\n{exc}", file=sys.stderr)
        return 2

    if _sin_incus():
        return 3

    respuesta = read_answer(ejercicio)
    incus = Incus(_runner())
    resultados: list[tuple[str, bool, str]] = []
    for check in ejercicio.checks:
        ok, detalle = run_check(check, incus, topo, respuesta)
        if ok:
            resultados.append((check.describe(), True, detalle))
        elif check.message:
            resultados.append((check.describe(), False, f"{check.message.strip()}\n          detail: {detalle}"))
        else:
            resultados.append((check.describe(), False, detalle))

    aciertos = sum(1 for _, ok, _ in resultados if ok)
    print(f"{ejercicio.id} - {ejercicio.title}")
    print(f"{aciertos}/{len(resultados)} checks passed\n")
    print(_informe(resultados))
    return 0 if aciertos == len(resultados) else 1


def cmd_answer(args) -> int:
    try:
        ejercicio = load_exercise(args.file)
    except LabErrors as exc:
        print(str(exc), file=sys.stderr)
        return 2
    ruta = write_answer(ejercicio, args.text)
    print(f"answer saved to {ruta}")
    return 0


def cmd_web(args) -> int:
    if args.file:
        topo = _cargar(args.file)
        try:
            nodos = [n.name for n in topo.resolve_profile(args.profile)]
        except KeyError:
            disponibles = ", ".join(sorted(topo.profiles)) or "(none)"
            print(f"error: profile {args.profile!r} does not exist. Available: {disponibles}", file=sys.stderr)
            return 2
    else:
        if _sin_incus():
            return 3
        nodos = [i.name for i in Incus(_runner()).listar()]

    if not nodos:
        print("error: no nodes to offer", file=sys.stderr)
        return 1

    from .web import make_server, serve

    servidor = make_server(nodos, host=args.host, port=args.port, token=args.token)
    host, puerto = servidor.server_address[:2]
    print(f"consoles at http://{host}:{puerto}  ({len(nodos)} nodes)")
    if args.token:
        print("token enabled: the URL must carry it in the token parameter")
    print("Ctrl-C to stop")
    serve(servidor)
    return 0


def cmd_image(args) -> int:
    from .images import build_plan, listar_imagenes, load_recipe

    if args.accion == "ls":
        if _sin_incus():
            return 3
        imagenes = listar_imagenes(_runner())
        if not imagenes:
            print("no custom images; build one with `lab image build <recipe>`")
            return 0
        for imagen in imagenes:
            print(imagen)
        return 0

    if args.accion == "rm":
        if _sin_incus():
            return 3
        res = _runner().run(["incus", "image", "delete", args.ref])
        if not res.ok:
            print(res.err.strip() or res.out.strip(), file=sys.stderr)
            return 1
        print(f"image {args.ref} deleted")
        return 0

    try:
        receta = load_recipe(args.recipe)
    except LabErrors as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        pasos = build_plan(receta)
    except (LabErrors, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"image {receta.referencia} from {receta.base} ({len(pasos)} steps)")
    if args.dry_run:
        for paso in pasos:
            if paso.kind != "push":
                print(f"-> {paso.command()}")
        return 0

    if _sin_incus():
        return 3

    from .engine import execute

    plan_falso = type("P", (), {"steps": pasos})()
    resultado = execute(plan_falso, _runner(), seguir=args.keep_going)
    print(resultado.resumen())
    for comando, error in resultado.fallos:
        print(f"  failed: {comando}", file=sys.stderr)
        if error:
            print(f"          {error}", file=sys.stderr)
    if resultado.ok:
        print(f"ready: `lab image ls` should show {receta.referencia}")
    return 0 if resultado.ok else 1


def cmd_images(args) -> int:
    for alias, ref in sorted(load_images().items()):
        print(f"{alias:<12} {ref}")
    return 0


def cmd_toolsets(args) -> int:
    for nombre, paquetes in sorted(load_toolsets().items()):
        print(f"{nombre:<10} {len(paquetes):>2} packages  {' '.join(paquetes)}")
    return 0


def cmd_init(args) -> int:
    destino = Path(args.name)
    if destino.exists():
        print(f"error: {destino} already exists", file=sys.stderr)
        return 1
    destino.mkdir(parents=True)
    plantilla = (Path(__file__).resolve().parents[2] / "lab" / "examples" / "pivot.yaml").read_text(
        encoding="utf-8"
    )
    plantilla = plantilla.replace("name: pivot-lab", f"name: {destino.name}", 1)
    (destino / "topology.yaml").write_text(plantilla, encoding="utf-8")
    print(f"created {destino}/topology.yaml - edit it and run: lab up {destino}/topology.yaml")
    return 0


# --------------------------------------------------------------------------- entrada


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lab",
        description="Network security lab: lightweight, declarative and reproducible.",
    )
    parser.add_argument("--version", action="version", version=f"netseclab {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("validate", help="validate one or more topologies")
    p.add_argument("files", nargs="+")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("render", help="show or save what `up` would do")
    p.add_argument("file")
    p.add_argument("--profile")
    p.add_argument("--format", choices=["shell", "json", "table"], default="table")
    p.add_argument("--out", help="write the generated files to a directory")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("up", help="bring the lab up")
    p.add_argument("file")
    p.add_argument("--profile")
    p.add_argument("--dry-run", action="store_true", help="only print the commands")
    p.add_argument("--keep-going", action="store_true", help="do not stop on the first error")
    p.add_argument("--no-snapshot", action="store_true", help="do not create the initial snapshot")
    p.set_defaults(func=cmd_up)

    p = sub.add_parser("down", help="stop the lab")
    p.add_argument("file")
    p.add_argument("names", nargs="*")
    p.add_argument("--profile")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_down)

    p = sub.add_parser("status", help="status of the instances")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("console", help="interactive console of a node")
    p.add_argument("name")
    p.set_defaults(func=cmd_console)

    p = sub.add_parser("snapshot", help="snapshot the current lab state")
    p.add_argument("file")
    p.add_argument("--name", default="snapshot")
    p.add_argument("--profile")
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("reset", help="return to the state of a snapshot")
    p.add_argument("file")
    p.add_argument("--name", default=SNAPSHOT_INICIAL)
    p.add_argument("--profile")
    p.set_defaults(func=cmd_reset)

    p = sub.add_parser("capture", help="capture traffic on a segment")
    p.add_argument("file")
    p.add_argument("--net", required=True, help="network name")
    p.add_argument("--seconds", type=int, default=15)
    p.add_argument("--out", help="output pcap file")
    p.set_defaults(func=cmd_capture)

    p = sub.add_parser("check", help="grade an exercise")
    p.add_argument("file")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("answer", help="save the reasoning answer of an exercise")
    p.add_argument("file")
    p.add_argument("text")
    p.set_defaults(func=cmd_answer)

    p = sub.add_parser("web", help="node consoles in the browser")
    p.add_argument("file", nargs="?", help="topology; if omitted, list the Incus instances")
    p.add_argument("--profile")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--token", help="require this token in the URL (recommended if you open it on a network)")
    p.set_defaults(func=cmd_web)

    p = sub.add_parser("images", help="image catalog")
    p.set_defaults(func=cmd_images)

    p = sub.add_parser("image", help="custom images: build, list and delete")
    sub_img = p.add_subparsers(dest="accion", required=True)
    b = sub_img.add_parser("build", help="build and publish an image from a recipe")
    b.add_argument("recipe")
    b.add_argument("--dry-run", action="store_true")
    b.add_argument("--keep-going", action="store_true")
    b.set_defaults(func=cmd_image)
    ls = sub_img.add_parser("ls", help="list custom images")
    ls.set_defaults(func=cmd_image)
    rm = sub_img.add_parser("rm", help="delete an image")
    rm.add_argument("ref")
    rm.set_defaults(func=cmd_image)

    p = sub.add_parser("toolsets", help="available tool sets")
    p.set_defaults(func=cmd_toolsets)

    p = sub.add_parser("init", help="create a topology template")
    p.add_argument("name")
    p.set_defaults(func=cmd_init)

    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:  # pragma: no cover - consolas exóticas
                pass
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
