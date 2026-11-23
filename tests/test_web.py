"""Pruebas del servidor de consolas, sin abrir un PTY de verdad."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from lab.web import FakeTerminal, make_server


@pytest.fixture
def servidor():
    terminales: list[FakeTerminal] = []

    def fabrica(_nodo: str) -> FakeTerminal:
        t = FakeTerminal(entrada=b"Debian GNU/Linux\nlab@nodo:~$ ")
        terminales.append(t)
        return t

    srv = make_server(["fw", "dmza"], host="127.0.0.1", port=0, fabrica=fabrica)
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    srv.terminales = terminales  # type: ignore[attr-defined]
    try:
        yield srv
    finally:
        srv.sala.cerrar_todo()
        srv.shutdown()
        srv.server_close()


def _url(servidor, ruta: str) -> str:
    host, puerto = servidor.server_address[:2]
    return f"http://{host}:{puerto}{ruta}"


def _get(servidor, ruta: str):
    with urllib.request.urlopen(_url(servidor, ruta), timeout=5) as r:
        return r.status, r.read(), dict(r.headers)


def _post(servidor, ruta: str, datos: dict | None = None):
    cuerpo = json.dumps(datos).encode() if datos is not None else b""
    peticion = urllib.request.Request(
        _url(servidor, ruta),
        data=cuerpo,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(peticion, timeout=5) as r:
        return r.status, json.loads(r.read() or b"{}")


def test_la_pagina_se_sirve(servidor):
    estado, cuerpo, _ = _get(servidor, "/")
    assert estado == 200
    assert b"netseclab" in cuerpo
    assert b"/api/open" in cuerpo


def test_lista_de_nodos(servidor):
    estado, cuerpo, _ = _get(servidor, "/api/nodes")
    assert estado == 200
    assert json.loads(cuerpo) == ["fw", "dmza"]


def test_abrir_y_leer_la_salida(servidor):
    _, datos = _post(servidor, "/api/open?node=fw")
    sid = datos["sid"]
    assert sid

    estado, cuerpo, cabeceras = _get(servidor, f"/api/out?sid={sid}&since=0")
    assert estado == 200
    assert b"Debian GNU/Linux" in cuerpo
    siguiente = int(cabeceras["X-Next"])
    assert siguiente > 0

    # desde el final ya no hay nada nuevo
    _, cuerpo2, _ = _get(servidor, f"/api/out?sid={sid}&since={siguiente}")
    assert cuerpo2 == b""


def test_escribir_llega_al_terminal(servidor):
    _, datos = _post(servidor, "/api/open?node=fw")
    sid = datos["sid"]
    _, respuesta = _post(servidor, "/api/in", {"sid": sid, "data": "id\r"})
    assert respuesta == {"ok": True}
    assert servidor.terminales[-1].escritos == [b"id\r"]


def test_cerrar_sesion(servidor):
    _, datos = _post(servidor, "/api/open?node=dmza")
    sid = datos["sid"]
    _, respuesta = _post(servidor, f"/api/close?sid={sid}")
    assert respuesta == {"cerrada": True}
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(servidor, f"/api/out?sid={sid}&since=0")
    assert exc.value.code == 404


def test_nodo_desconocido(servidor):
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(servidor, "/api/open?node=noexiste")
    assert exc.value.code == 404


def test_ruta_desconocida(servidor):
    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(servidor, "/no-existe")
    assert exc.value.code == 404


def test_token_protege_la_api_y_la_pagina():
    srv = make_server(
        ["fw"], host="127.0.0.1", port=0, token="secreto", fabrica=lambda _n: FakeTerminal()
    )
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    try:
        # sin token: 401
        with pytest.raises(urllib.error.HTTPError) as exc:
            _get(srv, "/api/nodes")
        assert exc.value.code == 401

        # con token: funciona
        estado, cuerpo, _ = _get(srv, "/api/nodes?token=secreto")
        assert estado == 200 and json.loads(cuerpo) == ["fw"]

        # La página lleva el token incrustado para que el navegador pueda usarlo: servirla sin
        # comprobarlo publicaba el token a quien la pidiera.
        with pytest.raises(urllib.error.HTTPError) as exc_pagina:
            _get(srv, "/")
        assert exc_pagina.value.code == 401
        assert b"secreto" not in exc_pagina.value.read()

        estado, pagina, _ = _get(srv, "/?token=secreto")
        assert estado == 200 and b"secreto" in pagina
    finally:
        srv.sala.cerrar_todo()
        srv.shutdown()
        srv.server_close()
