"""Caché de imágenes: publicar, listar y traer con verificación."""

from __future__ import annotations

import json

import pytest

from tynix.cache import (
    CachedImage,
    FileCache,
    HttpCache,
    digest_file,
    open_cache,
    verify,
)
from tynix.errors import CacheError


def _blob(tmp_path, contenido: bytes = b"imagen de prueba"):
    ruta = tmp_path / "origen.tar.gz"
    ruta.write_bytes(contenido)
    return ruta


def test_publicar_y_traer_una_imagen(tmp_path):
    cache = FileCache(tmp_path / "bucket")
    origen = _blob(tmp_path)
    entrada = cache.add("lab-node-v1", origen)

    assert entrada.sha256 == digest_file(origen)
    assert entrada.size == origen.stat().st_size
    assert [e.name for e in cache.list()] == ["lab-node-v1"]

    destino = tmp_path / "traida.tar.gz"
    cache.fetch(entrada, destino)
    assert destino.read_bytes() == origen.read_bytes()


def test_el_indice_es_un_json_legible(tmp_path):
    cache = FileCache(tmp_path / "bucket")
    cache.add("lab-web-v1", _blob(tmp_path))
    datos = json.loads((cache.root / "index.json").read_text(encoding="utf-8"))
    assert datos["version"] == 1
    assert datos["images"][0]["name"] == "lab-web-v1"


def test_una_imagen_corrupta_no_pasa(tmp_path):
    cache = FileCache(tmp_path / "bucket")
    origen = _blob(tmp_path)
    entrada = cache.add("lab-node-v1", origen)
    (cache.root / entrada.blob).write_bytes(b"manipulada")
    with pytest.raises(CacheError, match="does not match its checksum"):
        cache.fetch(entrada, tmp_path / "destino.tar.gz")


def test_traer_algo_que_no_esta(tmp_path):
    cache = FileCache(tmp_path / "bucket")
    with pytest.raises(CacheError, match="is not in the cache"):
        cache.fetch(CachedImage(name="x", sha256="0" * 64), tmp_path / "x")


def test_verificar_un_fichero_que_no_existe(tmp_path):
    with pytest.raises(CacheError, match="does not exist"):
        verify(tmp_path / "no-hay", CachedImage(name="x", sha256="0" * 64))


def test_publicar_dos_veces_actualiza_la_entrada(tmp_path):
    cache = FileCache(tmp_path / "bucket")
    cache.add("lab-node-v1", _blob(tmp_path, b"v1"))
    entrada = cache.add("lab-node-v1", _blob(tmp_path, b"v2"))
    assert len(cache.list()) == 1
    assert entrada.sha256 == digest_file(_blob(tmp_path, b"v2"))


def test_abrir_una_cache_por_url(tmp_path):
    assert isinstance(open_cache("https://bucket.universidad.edu/tynix/"), HttpCache)
    assert isinstance(open_cache(tmp_path), FileCache)


def test_la_url_se_construye_sobre_la_base():
    cache = HttpCache("https://bucket.universidad.edu/labs")
    assert cache._url("lab-node-v1.tar.gz") == (
        "https://bucket.universidad.edu/labs/lab-node-v1.tar.gz"
    )
