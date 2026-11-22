"""Cobertura de los comandos y rutas que aún no tenían pruebas."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import lab.cli as cli
from lab.engine import RecordingRunner
from lab.generate import netconf
from lab.model import load
from lab.plan import build

SNAPS_INITIAL = json.dumps([{"name": "initial"}])
SNAPS_OTRO = json.dumps([{"name": "otro"}])

EJEMPLOS = Path(__file__).resolve().parents[1] / "lab" / "examples"


def _incus_json(nombre: str, ips: list[str]) -> str:
    return json.dumps(
        [
            {
                "name": nombre,
                "status": "RUNNING",
                "type": "container",
                "state": {
                    "network": [
                        {
                            "address": f"eth{idx}",
                            "addresses": [
                                {"family": "inet", "address": ip, "scope": "global"}
                            ],
                        }
                        for idx, ip in enumerate(ips)
                    ]
                },
            }
        ]
    )


def test_status_muestra_estado_e_ips(monkeypatch, capsys):
    runner = RecordingRunner({"list --format json": (0, _incus_json("fw", ["10.5.0.254", "10.5.1.254"]), "")})
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    assert cli.main(["status"]) == 0
    salida = capsys.readouterr().out
    assert "fw" in salida and "RUNNING" in salida
    assert "10.5.0.254" in salida


def test_status_sin_instancias(monkeypatch, capsys):
    runner = RecordingRunner({"list --format json": (0, "[]", "")})
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    assert cli.main(["status"]) == 0
    assert "no instances" in capsys.readouterr().out


def test_console_delega_en_incus(monkeypatch, capsys):
    llamado: list[tuple] = []
    instancias = json.dumps([{"name": "dmza", "status": "RUNNING", "type": "container"}])
    runner = RecordingRunner({"list --format json": (0, instancias, "")})
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    monkeypatch.setattr(os, "execvp", lambda prog, args: llamado.append((prog, args)))
    assert cli.main(["console", "dmza"]) == 0
    assert llamado == [("incus", ["incus", "console", "dmza"])]
    # y avisa de cómo salir
    assert "Ctrl-a" in capsys.readouterr().err


def test_console_de_un_nodo_parado_muestra_el_log(monkeypatch, capsys):
    llamado: list[tuple] = []
    instancias = json.dumps([{"name": "dmza", "status": "STOPPED", "type": "container"}])
    runner = RecordingRunner({"list --format json": (0, instancias, "")})
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    monkeypatch.setattr(os, "execvp", lambda prog, args: llamado.append((prog, args)))
    assert cli.main(["console", "dmza"]) == 0
    assert llamado == [("incus", ["incus", "console", "--show-log", "dmza"])]
    assert "not running" in capsys.readouterr().err


def test_console_de_un_nodo_inexistente(monkeypatch, capsys):
    runner = RecordingRunner({"list --format json": (0, "[]", "")})
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    assert cli.main(["console", "noexiste"]) == 1
    assert "does not exist" in capsys.readouterr().err


def test_snapshot_crea_en_todos_los_nodos(monkeypatch, capsys):
    runner = RecordingRunner({"snapshot list": (0, "", "")})
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    codigo = cli.main(["snapshot", str(EJEMPLOS / "example.net.yaml"), "--profile", "mini", "--name", "antes"])
    assert codigo == 0
    assert runner.contiene("snapshot create fw antes")
    assert runner.contiene("snapshot create dmza antes")
    assert "snapshot 'antes'" in capsys.readouterr().out


def test_snapshot_informa_si_falla(monkeypatch, capsys):
    runner = RecordingRunner({"snapshot list": (0, "", ""), "snapshot create": (1, "", "disco lleno")})
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    assert cli.main(["snapshot", str(EJEMPLOS / "example.net.yaml"), "--profile", "mini"]) == 1
    assert "disco lleno" in capsys.readouterr().err


def test_reset_para_restaura_y_arranca(monkeypatch, capsys):
    runner = RecordingRunner({"incus query": (0, SNAPS_INITIAL, "")})
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    assert cli.main(["reset", str(EJEMPLOS / "example.net.yaml"), "--profile", "mini"]) == 0
    assert runner.contiene("incus stop fw")
    assert runner.contiene("snapshot restore fw initial")
    assert runner.contiene("incus start fw")


# --------------------------------------------------------------------------- rutas por enlace


def test_las_rutas_declaradas_en_un_enlace_se_aplican(workdir):
    ruta = workdir / "rutas.yaml"
    ruta.write_text(
        """
version: 1
name: rutas
networks:
  lan: { cidr: 10.0.1.0/24, gateway: 10.0.1.1 }
nodes:
  - name: r
    links:
      - net: lan
        ip: 10.0.1.1
        routes:
          - { to: 10.9.0.0/24, via: 10.0.1.254 }
  - name: otro
    links: [lan]
""",
        encoding="utf-8",
    )
    topo = load(ruta)
    guion = netconf.net_script(topo, topo.node("r"))
    assert "ip route replace 10.9.0.0/24 via 10.0.1.254 dev eth0" in guion


def test_una_ruta_mal_escrita_es_un_error(workdir):
    ruta = workdir / "rutas-malas.yaml"
    ruta.write_text(
        """
version: 1
name: rutas-malas
networks: { lan: { cidr: 10.0.1.0/24 } }
nodes:
  - name: r
    links:
      - net: lan
        routes:
          - { to: 10.9.0.0/33, via: 10.0.1.254 }
""",
        encoding="utf-8",
    )
    from lab.errors import LabErrors

    with pytest.raises(LabErrors, match="invalid destination"):
        load(ruta)


def test_el_plan_incluye_las_rutas_en_el_script_del_nodo(workdir):
    ruta = workdir / "rutas2.yaml"
    ruta.write_text(
        """
version: 1
name: rutas2
networks: { lan: { cidr: 10.0.2.0/24 } }
nodes:
  - name: r
    links:
      - net: lan
        ip: 10.0.2.1
        routes:
          - { to: 10.8.0.0/16, via: 10.0.2.254 }
""",
        encoding="utf-8",
    )
    plan = build(load(ruta))
    scripts = [s.content for s in plan.steps if s.kind == "push" and s.path.endswith("lab-net")]
    assert any("10.8.0.0/16 via 10.0.2.254" in s for s in scripts)


# --------------------------------------------------------------------------- VLANs


def test_la_vlan_del_enlace_llega_al_dispositivo(workdir):
    ruta = workdir / "vlan.yaml"
    ruta.write_text(
        """
version: 1
name: vlan
networks: { lan: { cidr: 10.0.3.0/24 } }
nodes:
  - name: a
    links:
      - { net: lan, vlan: 42 }
""",
        encoding="utf-8",
    )
    plan = build(load(ruta))
    dispositivos = [s.command() for s in plan.steps if s.kind == "cmd" and "device add" in s.command()]
    assert any("vlan=42" in d for d in dispositivos)


def test_una_vlan_fuera_de_rango_es_un_error(workdir):
    ruta = workdir / "vlan-mala.yaml"
    ruta.write_text(
        """
version: 1
name: vlan-mala
networks: { lan: { cidr: 10.0.4.0/24 } }
nodes:
  - name: a
    links:
      - { net: lan, vlan: 5000 }
""",
        encoding="utf-8",
    )
    from lab.errors import LabErrors

    with pytest.raises(LabErrors, match="between 1 and 4094"):
        load(ruta)


def test_la_vlan_de_red_no_se_acepta(workdir):
    """La VLAN es por enlace; a nivel de red sería una opción que no hace nada."""
    ruta = workdir / "vlan-red.yaml"
    ruta.write_text(
        """
version: 1
name: vlan-red
networks:
  lan: { cidr: 10.0.5.0/24, vlan: 10 }
nodes:
  - { name: a, links: [lan] }
""",
        encoding="utf-8",
    )
    from lab.errors import LabErrors

    with pytest.raises(LabErrors, match="unknown key"):
        load(ruta)


def test_status_entiende_el_json_con_mapa_de_interfaces(monkeypatch, capsys):
    """Incus devuelve state.network como mapa nombre->interfaz, no como lista."""
    datos = json.dumps(
        [
            {
                "name": "fw",
                "status": "RUNNING",
                "type": "container",
                "state": {
                    "network": {
                        "eth0": {
                            "addresses": [
                                {"family": "inet", "address": "10.5.0.254", "scope": "global"}
                            ]
                        },
                        "eth1": {
                            "addresses": [
                                {"family": "inet", "address": "10.5.1.254", "scope": "global"}
                            ]
                        },
                    }
                },
            }
        ]
    )
    runner = RecordingRunner({"list --format json": (0, datos, "")})
    monkeypatch.setattr(cli, "_runner", lambda: runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/incus")
    assert cli.main(["status"]) == 0
    salida = capsys.readouterr().out
    assert "10.5.0.254" in salida and "10.5.1.254" in salida


def test_los_ajustes_del_bridge_necesitan_root(workdir):
    """Cambiar puertos del bridge y hablar con OVS requiere privilegios."""
    ruta = workdir / "hub.yaml"
    ruta.write_text(
        """
version: 1
name: hub
networks:
  ext: { cidr: 10.7.0.0/24, mode: hub }
nodes:
  - { name: a, links: [ext] }
""",
        encoding="utf-8",
    )
    plan = build(load(ruta))
    post = [s.command() for s in plan.steps if s.phase == "post"]
    assert post and all(c.startswith("sudo ") for c in post)
