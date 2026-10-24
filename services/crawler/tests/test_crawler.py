import httpx
import pytest
from crawler_svc.fetcher import BlockedByRobots, PoliteFetcher
from crawler_svc.rawstore import MemoryRawStore
from crawler_svc.runner import run_spider
from crawler_svc.spiders import FixtureSpider
from morbidus_common.bus import InMemoryBus
from morbidus_common.events import Topics


async def test_fixture_publica_so_dados_do_falecido():
    bus, store = InMemoryBus(), MemoryRawStore()
    fetcher = PoliteFetcher("teste", 0)
    total = await run_spider(FixtureSpider(), fetcher, store, bus)
    await fetcher.aclose()

    assert total == 3
    assert len(store.objects) == 1
    eventos = [p for t, p in bus.published if t == Topics.OBITUARY_RAW]
    primeiro = eventos[0]
    assert primeiro["nome"] == "Fulano de Tal da Silva"
    assert primeiro["idade"] == "82 anos"
    assert primeiro["uf"] == "PR"
    # O texto livre com nomes de parentes não pode vazar para o evento.
    assert "Maria" not in str(eventos)


async def test_recoleta_gera_mesmos_event_ids():
    bus = InMemoryBus()
    fetcher = PoliteFetcher("teste", 0)
    await run_spider(FixtureSpider(), fetcher, MemoryRawStore(), bus)
    await run_spider(FixtureSpider(), fetcher, MemoryRawStore(), bus)
    await fetcher.aclose()
    ids = [p["event_id"] for _, p in bus.published]
    assert len(ids) == 6 and len(set(ids)) == 3


def test_file_raw_store_grava_e_bloqueia_path_traversal(tmp_path):
    from crawler_svc.rawstore import FileRawStore

    store = FileRawStore(str(tmp_path))
    store.put("fonte/2026/10/24/abc.html", b"<html></html>")
    assert (tmp_path / "fonte/2026/10/24/abc.html").read_bytes() == b"<html></html>"
    with pytest.raises(ValueError):
        store.put("../fora.html", b"x")


def test_file_raw_store_apaga_paginas_antigas(tmp_path):
    import os
    import time

    from crawler_svc.rawstore import FileRawStore

    store = FileRawStore(str(tmp_path))
    store.put("fonte/2026/08/01/velha.html", b"velha")
    store.put("fonte/2026/10/24/nova.html", b"nova")
    velha = tmp_path / "fonte/2026/08/01/velha.html"
    quarenta_dias = time.time() - 40 * 86400
    os.utime(velha, (quarenta_dias, quarenta_dias))

    assert store.purge(30) == 1
    assert not velha.exists() and not (tmp_path / "fonte/2026/08").exists()
    assert (tmp_path / "fonte/2026/10/24/nova.html").exists()


async def test_fetcher_respeita_robots():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /privado\n")
        return httpx.Response(200, text="ok")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    fetcher = PoliteFetcher("MORBiDusBot", 0, client=client)
    assert await fetcher.get("https://jornal.exemplo/falecimentos") == "ok"
    with pytest.raises(BlockedByRobots):
        await fetcher.get("https://jornal.exemplo/privado/lista")
    await fetcher.aclose()
