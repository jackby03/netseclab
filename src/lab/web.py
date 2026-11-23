"""Consolas por navegador, sin dependencias.

Un servidor HTTP mínimo dentro de la caja: abre un PTY por nodo (`incus exec -t <nodo> -- bash -l`),
acumula su salida y la sirve por sondeo. Nada de WebSockets ni de xterm.js: el navegador del
anfitrión solo tiene que poder llegar a `http://<caja>:8080`.

Se ata a 127.0.0.1 por defecto. Exponerlo en red es una decisión consciente del usuario: da una
shell dentro del laboratorio.
"""

from __future__ import annotations

import contextlib
import json
import os
import select
import shlex
import struct
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Protocol
from urllib.parse import parse_qs, urlparse

try:  # pty y termios no existen en Windows
    import pty
    import termios

    TIENE_PTY = True
except ImportError:  # pragma: no cover - depende de la plataforma
    pty = None  # type: ignore[assignment]
    termios = None  # type: ignore[assignment]
    TIENE_PTY = False

FILAS, COLUMNAS = 30, 100
LIMITE_SALIDA = 256 * 1024  # bytes de scrollback por sesión


# --------------------------------------------------------------------------- terminales


class Terminal(Protocol):
    alive: bool

    def read(self, timeout: float) -> bytes: ...
    def write(self, data: bytes) -> None: ...
    def close(self) -> None: ...


class PtyTerminal:
    """Proceso real colgado de un pseudo-terminal."""

    def __init__(self, argv: list[str], filas: int = FILAS, columnas: int = COLUMNAS):
        if not TIENE_PTY:
            raise RuntimeError("las consolas con PTY necesitan Linux; en Windows usa `lab console`")
        self.master, esclavo = pty.openpty()
        try:
            import fcntl

            fcntl.ioctl(
                self.master,
                termios.TIOCSWINSZ,
                struct.pack("HHHH", filas, columnas, 0, 0),
            )
        except OSError:  # pragma: no cover - depende de la plataforma
            pass
        self.proc = subprocess.Popen(
            argv,
            stdin=esclavo,
            stdout=esclavo,
            stderr=esclavo,
            close_fds=True,
            start_new_session=True,
        )
        os.close(esclavo)
        self.alive = True

    def read(self, timeout: float) -> bytes:
        listos, _, _ = select.select([self.master], [], [], timeout)
        if not listos:
            return b""
        try:
            datos = os.read(self.master, 4096)
        except OSError:
            datos = b""
        if not datos:
            self.alive = False
        return datos

    def write(self, datos: bytes) -> None:
        try:
            os.write(self.master, datos)
        except OSError:
            self.alive = False

    def close(self) -> None:
        self.alive = False
        with contextlib.suppress(Exception):  # mejor esfuerzo al cerrar
            self.proc.terminate()
            self.proc.wait(timeout=2)
        if self.proc.poll() is None:
            with contextlib.suppress(Exception):
                self.proc.kill()
        with contextlib.suppress(OSError):
            os.close(self.master)


@dataclass
class FakeTerminal:
    """Terminal de pruebas: devuelve lo que se le haya cargado."""

    entrada: bytes = b""
    alive: bool = True
    escritos: list[bytes] = field(default_factory=list)

    def read(self, timeout: float) -> bytes:
        if self.entrada:
            datos, self.entrada = self.entrada, b""
            return datos
        self.alive = False
        return b""

    def write(self, datos: bytes) -> None:
        self.escritos.append(datos)

    def close(self) -> None:
        self.alive = False


# --------------------------------------------------------------------------- sesiones


@dataclass
class Session:
    terminal: Terminal
    salida: bytearray = field(default_factory=bytearray)
    cerrada: bool = False
    base: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        self._hilo = threading.Thread(target=self._bombear, daemon=True)
        self._hilo.start()

    def _bombear(self) -> None:
        while not self.cerrada:
            trozo = self.terminal.read(0.2)
            if trozo:
                self._guardar(trozo)
                continue
            if not self.terminal.alive:
                break
        self.cerrada = True

    def _guardar(self, trozo: bytes) -> None:
        """Acumula salida con un tope: una consola abierta horas no debe comerse la memoria."""
        with self._lock:
            self.salida.extend(trozo)
            if len(self.salida) > LIMITE_SALIDA:
                sobra = len(self.salida) - LIMITE_SALIDA
                del self.salida[:sobra]
                self.base += sobra

    def desde(self, posicion: int) -> tuple[bytes, int]:
        with self._lock:
            inicio = max(0, posicion - self.base)
            return bytes(self.salida[inicio:]), self.base + len(self.salida)

    def escribir(self, datos: bytes) -> None:
        self.terminal.write(datos)

    def cerrar(self) -> None:
        self.cerrada = True
        self.terminal.close()


class Sala:
    """Conjunto de sesiones abiertas, una por pestaña."""

    def __init__(self, fabrica: Callable[[str], Terminal]):
        self.fabrica = fabrica
        self.sesiones: dict[str, Session] = {}
        self._contador = 0
        self._lock = threading.Lock()

    def abrir(self, nodo: str) -> str:
        with self._lock:
            self._contador += 1
            sid = f"s{self._contador}"
        self.sesiones[sid] = Session(self.fabrica(nodo))
        return sid

    def obtener(self, sid: str) -> Session | None:
        return self.sesiones.get(sid)

    def cerrar(self, sid: str) -> bool:
        session = self.sesiones.pop(sid, None)
        if session is None:
            return False
        session.cerrar()
        return True

    def cerrar_todo(self) -> None:
        for sid in list(self.sesiones):
            self.cerrar(sid)


# --------------------------------------------------------------------------- servidor


def fabrica_incus(nodo: str, shell: str = "bash -l", filas: int = FILAS, columnas: int = COLUMNAS):
    argv = ["incus", "exec", "-t", nodo, "--", *shlex.split(shell)]
    return PtyTerminal(argv, filas=filas, columnas=columnas)


PAGINA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>netseclab — consolas</title>
<style>
 body{font-family:system-ui,sans-serif;margin:0;display:flex;height:100vh;background:#111;color:#ddd}
 nav{width:180px;background:#1b1b1b;padding:.6rem;overflow:auto}
 nav h1{font-size:.9rem;margin:.2rem 0 .8rem;color:#8ad}
 nav button{display:block;width:100%;margin:.15rem 0;padding:.4rem;text-align:left;
   background:#262626;color:#ddd;border:1px solid #333;border-radius:4px;cursor:pointer}
 nav button:hover{background:#333}
 main{flex:1;display:flex;flex-direction:column;padding:.5rem;min-width:0}
 #term{flex:1;margin:0;padding:.6rem;background:#000;color:#d6ffd6;overflow:auto;
   font:13px/1.35 ui-monospace,Consolas,monospace;white-space:pre-wrap;word-break:break-all}
 #estado{font-size:.8rem;color:#888;padding:.2rem 0}
</style></head>
<body>
<nav><h1>nodos</h1><div id="nodes"></div></nav>
<main><div id="estado">elige un nodo</div><pre id="term"></pre></main>
<script>
let sid = null, since = 0, timer = null;
const TOKEN = "__TOKEN__";
const q = (...p) => p.join('&') + (TOKEN ? '&token=' + encodeURIComponent(TOKEN) : '');

async function cargarNodos() {
  const r = await fetch('/api/nodes?' + q());
  const nodos = await r.json();
  const cont = document.getElementById('nodes');
  cont.innerHTML = '';
  for (const n of nodos) {
    const b = document.createElement('button');
    b.textContent = n;
    b.onclick = () => abrir(n);
    cont.appendChild(b);
  }
}

async function abrir(nodo) {
  if (sid) await cerrar();
  const r = await fetch('/api/open?' + q('node=' + encodeURIComponent(nodo)), {method:'POST'});
  const d = await r.json();
  if (d.error) { document.getElementById('estado').textContent = d.error; return; }
  sid = d.sid; since = 0;
  document.getElementById('term').textContent = '';
  document.getElementById('estado').textContent = nodo + ' — ' + sid;
  timer = setInterval(leer, 150);
  document.getElementById('term').focus();
}

async function leer() {
  if (!sid) return;
  const r = await fetch('/api/out?' + q(`sid=${sid}&since=${since}`));
  if (!r.ok) return;
  const texto = await r.text();
  since = parseInt(r.headers.get('X-Next') || since);
  if (texto) {
    const t = document.getElementById('term');
    t.textContent += texto;
    t.scrollTop = t.scrollHeight;
  }
}

async function enviar(datos) {
  if (!sid) return;
  await fetch('/api/in?' + q(), {method:'POST', body: JSON.stringify({sid, data: datos})});
}

async function cerrar() {
  if (timer) clearInterval(timer);
  if (sid) await fetch('/api/close?' + q('sid=' + sid), {method:'POST'});
  sid = null; timer = null;
}

document.addEventListener('keydown', e => {
  if (!sid) return;
  let d = null;
  if (e.key === 'Enter') d = '\\r';
  else if (e.key === 'Backspace') d = '\\u007f';
  else if (e.key === 'Tab') d = '\\t';
  else if (e.key === 'Escape') d = '\\u001b';
  else if (e.ctrlKey && e.key.length === 1) d = String.fromCharCode(e.key.toUpperCase().charCodeAt(0) - 64);
  else if (e.key.length === 1) d = e.key;
  if (d !== null) { e.preventDefault(); enviar(d); }
});

window.addEventListener('beforeunload', cerrar);
cargarNodos();
</script>
</body></html>
"""


class Manejador(BaseHTTPRequestHandler):
    server: Servidor

    def log_message(self, formato: str, *args) -> None:  # silencio
        pass

    # ---------------------------------------------------------------- ayudas

    def _json(self, datos: dict, codigo: int = 200) -> None:
        cuerpo = json.dumps(datos).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _texto(self, cuerpo: bytes, extra: dict[str, str] | None = None, codigo: int = 200) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        for clave, valor in (extra or {}).items():
            self.send_header(clave, valor)
        self.end_headers()
        self.wfile.write(cuerpo)

    def _cuerpo(self) -> bytes:
        longitud = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(longitud) if longitud else b""

    def _autorizado(self, ruta) -> bool:
        if not self.server.token:
            return True
        enviado = (parse_qs(ruta.query).get("token") or [""])[0]
        return enviado == self.server.token

    # ---------------------------------------------------------------- rutas

    def do_GET(self) -> None:
        ruta = urlparse(self.path)
        if ruta.path.startswith("/api/") and not self._autorizado(ruta):
            self._json({"error": "token no válido"}, codigo=401)
            return
        if ruta.path in ("/", "/index.html"):
            pagina = PAGINA.replace("__TOKEN__", self.server.token or "")
            self._texto(pagina.encode("utf-8"))
            return
        if ruta.path == "/api/nodes":
            self._json(self.server.nodos)
            return
        if ruta.path == "/api/out":
            consulta = parse_qs(ruta.query)
            sid = (consulta.get("sid") or [""])[0]
            since = int((consulta.get("since") or ["0"])[0] or 0)
            session = self.server.sala.obtener(sid)
            if session is None:
                self._json({"error": "sesión cerrada"}, codigo=404)
                return
            datos, siguiente = session.desde(since)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(datos)))
            self.send_header("X-Next", str(siguiente))
            self.end_headers()
            self.wfile.write(datos)
            return
        self._json({"error": "no encontrado"}, codigo=404)

    def do_POST(self) -> None:
        ruta = urlparse(self.path)
        if ruta.path.startswith("/api/") and not self._autorizado(ruta):
            self._json({"error": "token no válido"}, codigo=401)
            return
        if ruta.path == "/api/open":
            nodo = (parse_qs(ruta.query).get("node") or [""])[0]
            if nodo not in self.server.nodos:
                self._json({"error": f"el nodo {nodo!r} no existe"}, codigo=404)
                return
            self._json({"sid": self.server.sala.abrir(nodo)})
            return
        if ruta.path == "/api/in":
            try:
                datos = json.loads(self._cuerpo() or b"{}")
            except json.JSONDecodeError:
                self._json({"error": "cuerpo no válido"}, codigo=400)
                return
            session = self.server.sala.obtener(str(datos.get("sid", "")))
            if session is None:
                self._json({"error": "sesión cerrada"}, codigo=404)
                return
            session.escribir(str(datos.get("data", "")).encode("utf-8"))
            self._json({"ok": True})
            return
        if ruta.path == "/api/close":
            sid = (parse_qs(ruta.query).get("sid") or [""])[0]
            self._json({"cerrada": self.server.sala.cerrar(sid)})
            return
        self._json({"error": "no encontrado"}, codigo=404)


class Servidor(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, direccion, nodos: list[str], sala: Sala, token: str | None = None):
        super().__init__(direccion, Manejador)
        self.nodos = nodos
        self.sala = sala
        self.token = token


def make_server(
    nodos: list[str],
    host: str = "127.0.0.1",
    port: int = 8080,
    fabrica: Callable[[str], Terminal] | None = None,
    token: str | None = None,
) -> Servidor:
    sala = Sala(fabrica or fabrica_incus)
    return Servidor((host, port), nodos, sala, token=token)


def serve(server: Servidor) -> None:
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.sala.cerrar_todo()
        server.server_close()
