"""Pruebas del motor: ejecución idempotente, snapshots y captura."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab.engine import Incus, RecordingRunner, execute, restore_snapshot, take_snapshot
from lab.engine.capture import plan_capture, run_capture
from lab.model import load
from lab.plan import build

EJEMPLOS = Path(__file__).resolve().parents[1] / "lab" / "examples"


@pytest.fixture(scope="module")
def example_net():
    return load(EJEMPLOS / "example.net.yaml")


@pytest.fixture(scope="module")
def plan(example_net):
    return build(example_net, profile="mini")


def test_ejecuta_todo_cuando_no_hay_errores(plan):
    runner = RecordingRunner()
    outcome = execute(plan, runner)
    assert outcome.ok
    assert outcome.ejecutados >= 10
    assert outcome.omitidos == 0


def test_lo_que_ya_existe_no_es_un_fallo(plan):
    runner = RecordingRunner({"network create": (1, "", "Error: network already exists")})
    outcome = execute(plan, runner)
    assert outcome.ok
    assert outcome.omitidos == 3  # las tres redes
    assert not outcome.fallos


def test_relanzar_una_instancia_existente_no_es_un_fallo(plan):
    """Incus responde con una violación de unicidad, no con 'already exists'."""
    runner = RecordingRunner(
        {"incus launch": (1, "", "UNIQUE constraint failed: instances.project_id, instances.name")}
    )
    outcome = execute(plan, runner)
    assert outcome.ok
    assert outcome.omitidos == len(plan.nodes)
    assert not outcome.fallos


def test_un_error_de_verdad_para_el_plan(plan):
    runner = RecordingRunner({"device add": (1, "", "invalid mac address")})
    outcome = execute(plan, runner)
    assert not outcome.ok
    assert len(outcome.fallos) == 1
    assert "invalid mac" in outcome.fallos[0][1]


def test_keep_going_continua_tras_el_fallo(plan):
    runner = RecordingRunner({"config device add": (1, "", "boom")})
    outcome = execute(plan, runner, seguir=True)
    assert not outcome.ok
    # sin keep-going se pararía en el primer device; con keep-going fallan todos
    assert len(outcome.fallos) == 5
    assert outcome.ejecutados > 5


def _snaps(*nombres: str) -> str:
    return json.dumps([{"name": n} for n in nombres])


def test_snapshot_inicial(example_net):
    runner = RecordingRunner({"incus query": (1, "", "no existe")})
    incus = Incus(runner)
    fallos = take_snapshot(incus, ["fw", "dmza"], "initial")
    assert fallos == []
    assert runner.contiene("snapshot create fw initial")
    assert runner.contiene("snapshot create dmza initial")


def test_no_repite_un_snapshot_que_ya_existe():
    runner = RecordingRunner({"incus query": (0, _snaps("initial"), "")})
    incus = Incus(runner)
    take_snapshot(incus, ["fw"], "initial")
    assert not runner.contiene("snapshot create")


def test_restore_avisa_si_falta_el_snapshot():
    runner = RecordingRunner({"incus query": (0, _snaps("otro"), "")})
    fallos = restore_snapshot(Incus(runner), ["fw"], "initial")
    assert len(fallos) == 1
    assert "no existe el snapshot" in fallos[0]
    # si no existe, no se intenta restaurar
    assert not runner.contiene("snapshot restore")
    assert runner.contiene("incus query")


def test_los_snapshots_pueden_venir_como_urls():
    """La API devuelve a veces rutas, no objetos con nombre."""
    runner = RecordingRunner(
        {"incus query": (0, json.dumps(["/1.0/instances/fw/snapshots/initial"]), "")}
    )
    assert Incus(runner).snapshots("fw") == ["initial"]


def test_captura_en_red_espejo(example_net):
    red = example_net.networks["dmz"]
    plan = plan_capture(example_net, red, 5, Path("capture/dmz.pcap"))
    assert plan.modo == "mirror"
    assert "cap-dmz" in plan.comandos[0]
    # el puerto espejo vive en el anfitrión: hace falta root
    assert plan.comandos[0][:3] == ["sudo", "timeout", "5"]


def test_captura_en_red_hub_desde_un_nodo(example_net):
    red = example_net.networks["ext"]
    plan = plan_capture(example_net, red, 5, Path("capture/ext.pcap"))
    assert plan.modo == "hub"
    assert "promisc" in plan.comandos[0]
    assert any("tcpdump" in c for c in plan.comandos[1])
    assert "file pull" in " ".join(plan.comandos[2])


def test_captura_tolera_el_timeout_de_tcpdump(example_net):
    plan = plan_capture(example_net, example_net.networks["ext"], 3, Path("x.pcap"))
    runner = RecordingRunner({"tcpdump": (124, "", "")})
    ok, _ = run_capture(plan, runner)
    assert ok


def test_captura_falla_si_tcpdump_no_existe(example_net):
    plan = plan_capture(example_net, example_net.networks["ext"], 3, Path("x.pcap"))
    runner = RecordingRunner({"tcpdump": (127, "", "command not found")})
    ok, detalle = run_capture(plan, runner)
    assert not ok
    assert "not found" in detalle
