"""Pruebas de las comprobaciones: gramática y ejecución."""

from __future__ import annotations

from pathlib import Path

import pytest

from lab.checks import parse_check, run_check
from lab.engine import Incus, RecordingRunner
from lab.errors import LabErrors
from lab.exercise import load as load_exercise
from lab.model import load

RAIZ = Path(__file__).resolve().parents[1]
EJERCICIO = RAIZ / "lab" / "exercises" / "06-fuzz-evasion.yaml"


@pytest.fixture(scope="module")
def topo():
    return load(RAIZ / "lab" / "examples" / "fuzz-evasion.yaml")


def _check(texto: str):
    return parse_check({"assert": texto}, "checks[0]")


def test_gramatica_port_state():
    c = _check("port-state exta -> 10.5.1.10:443 is closed")
    assert c.kind == "port-state"
    assert c.params == {"from": "exta", "target": "10.5.1.10", "port": 443, "expect": "closed"}


def test_gramatica_reachable():
    c = _check("reachable inta -> exta is true")
    assert c.params["expect"] is True


def test_gramatica_http_status():
    c = _check("http-status evil1 -> http://www.lab/admin/ is 200")
    assert c.params["expect"] == 200


def test_gramatica_file():
    c = _check("file www /var/www/html/.git/config exists")
    assert c.params["path"].endswith(".git/config")


def test_gramatica_ids_alerts():
    c = _check("ids-alerts src=10.20.0.30, count=0")
    assert c.kind == "ids-alerts"
    assert c.params["src"] == "10.20.0.30"
    assert c.params["count"] == 0


def test_gramatica_capture():
    c = _check('capture dmz, contains: "GET /admin/"')
    assert c.params["net"] == "dmz"
    assert c.params["contains"] == "GET /admin/"


def test_un_parametro_no_admitido_falla():
    with pytest.raises(LabErrors, match="not allowed"):
        _check("ids-alerts since=last, count=0")
    with pytest.raises(LabErrors, match="not allowed"):
        _check('capture dmz, since=last, contains: "x"')


def test_la_respuesta_ya_no_es_un_tipo_de_comprobacion():
    """Un valor concreto va en `answers`, no en `checks`."""
    with pytest.raises(LabErrors, match="unknown check"):
        _check('answer "¿Por qué?" contains "reject"')


def test_una_comprobacion_inventada_falla():
    with pytest.raises(LabErrors, match="unknown check"):
        _check("haz magia con el cortafuegos")


def test_reachable_ok(topo):
    check = _check("reachable evil1 -> www.lab is true")
    runner = RecordingRunner({"ping": (0, "1 received", "")})
    ok, detalle = run_check(check, Incus(runner), topo)
    assert ok, detalle


def test_reachable_esperado_falso(topo):
    check = _check("reachable evil1 -> inta is false")
    runner = RecordingRunner({"ping": (1, "", "100% packet loss")})
    ok, _ = run_check(check, Incus(runner), topo)
    assert ok


def test_port_state_abierto(topo):
    check = _check("port-state evil1 -> 10.20.1.10:80 is open")
    runner = RecordingRunner({"/dev/tcp/10.20.1.10/80": (0, "", "")})
    ok, detalle = run_check(check, Incus(runner), topo)
    assert ok and "open" in detalle


def test_port_state_cerrado(topo):
    check = _check("port-state evil1 -> 10.20.1.10:443 is closed")
    runner = RecordingRunner({"/dev/tcp/10.20.1.10/443": (1, "", "refused")})
    ok, detalle = run_check(check, Incus(runner), topo)
    assert ok and "closed" in detalle


def test_port_state_filtrado(topo):
    check = _check("port-state evil1 -> 10.20.1.10:22 is filtered")
    runner = RecordingRunner({"/dev/tcp/10.20.1.10/22": (124, "", "")})
    ok, detalle = run_check(check, Incus(runner), topo)
    assert ok and "filtered" in detalle


def test_http_status(topo):
    check = _check("http-status evil1 -> http://10.20.1.10/backup/ is 200")
    runner = RecordingRunner({"curl": (0, "200", "")})
    ok, detalle = run_check(check, Incus(runner), topo)
    assert ok and "200" in detalle


def test_file_existe(topo):
    check = _check("file www /var/www/html/backup/db.sql exists")
    runner = RecordingRunner({"test -e": (0, "", "")})
    ok, _ = run_check(check, Incus(runner), topo)
    assert ok


def test_ids_sin_alertas(topo):
    check = _check("ids-alerts src: 10.20.0.30, count: 0")
    runner = RecordingRunner({"grep": (0, "0\n", "")})
    ok, detalle = run_check(check, Incus(runner), topo)
    assert ok and "0 alerts" in detalle
    # el nodo del IDS se deduce de la topología
    assert runner.contiene("exec fw")


def test_ids_con_alertas(topo):
    check = _check("ids-alerts src: 10.20.0.30, count: 3")
    runner = RecordingRunner({"grep": (0, "3\n", "")})
    ok, _ = run_check(check, Incus(runner), topo)
    assert ok


def test_captura_sin_fichero(topo, workdir):
    check = parse_check(
        {"assert": f'capture dmz, contains: "GET /admin/", file: {workdir}/no.pcap'},
        "checks[0]",
    )
    ok, detalle = run_check(check, Incus(RecordingRunner()), topo)
    assert not ok
    assert "does not exist" in detalle


def test_captura_encuentra_el_texto(topo, workdir):
    pcap = workdir / "dmz.pcap"
    pcap.write_bytes(b"....GET /admin/ HTTP/1.1....")
    check = parse_check(
        {"assert": f'capture dmz, contains: "GET /admin/", file: {pcap}'}, "checks[0]"
    )
    ok, _ = run_check(check, Incus(RecordingRunner()), topo)
    assert ok


def test_el_ejercicio_de_ejemplo_se_carga():
    ejercicio = load_exercise(EJERCICIO)
    assert ejercicio.id == "06-fuzz-evasion"
    assert ejercicio.lab.name == "fuzz-evasion.yaml"
    assert len(ejercicio.checks) == 3
    assert {c.kind for c in ejercicio.checks} >= {"http-status", "file", "ids-alerts"}
    assert [a.id for a in ejercicio.answers] == ["cabecera-delatora"]
    assert ejercicio.points == 5
    assert "respaldo" in ejercicio.brief
    assert "agente de usuario" in ejercicio.hints[0]


def test_un_ejercicio_sin_comprobaciones_falla(workdir):
    ruta = workdir / "vacio.yaml"
    ruta.write_text("id: x\ntitle: X\nlab: ../x.yaml\n", encoding="utf-8")
    with pytest.raises(LabErrors) as exc:
        load_exercise(ruta)
    assert "at least one check" in str(exc.value)


def test_todos_los_ejercicios_del_repositorio_cargan():
    rutas = sorted((RAIZ / "lab" / "exercises").glob("*.yaml"))
    assert len(rutas) >= 3
    for ruta in rutas:
        ejercicio = load_exercise(ruta)
        assert ejercicio.checks, ruta
        # el laboratorio al que apunta tiene que existir y ser válido
        load(ejercicio.lab)
