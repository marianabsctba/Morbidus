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


async def test_fetcher_tenta_de_novo_em_falha_passageira():
    chamadas = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            raise httpx.ConnectTimeout("demorou")
        if chamadas["n"] == 2:
            return httpx.Response(503)
        return httpx.Response(200, text="ok")

    fetcher = PoliteFetcher("teste", 0, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert await fetcher.get("https://site.exemplo/lista") == "ok"
    assert chamadas["n"] == 3
    await fetcher.aclose()


async def test_fetcher_desiste_depois_das_tentativas():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        raise httpx.ConnectTimeout("fora do ar")

    fetcher = PoliteFetcher("teste", 0, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), tentativas=2)
    with pytest.raises(httpx.ConnectTimeout):
        await fetcher.get("https://site.exemplo/lista")
    await fetcher.aclose()


async def test_robots_com_erro_de_servidor_bloqueia():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503) if request.url.path == "/robots.txt" else httpx.Response(200, text="ok")

    fetcher = PoliteFetcher("teste", 0, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), tentativas=2)
    with pytest.raises(BlockedByRobots):
        await fetcher.get("https://site.exemplo/lista")
    await fetcher.aclose()


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


def test_lista_de_fontes_so_para_admin():
    from crawler_svc.config import CrawlerSettings
    from crawler_svc.main import build_app
    from fastapi.testclient import TestClient

    client = TestClient(build_app(CrawlerSettings(enabled_spiders="fixture"), bus=InMemoryBus()))
    assert client.get("/v1/sources", headers={"X-Tenant-Id": "t1"}).status_code == 403
    assert client.get("/v1/sources", headers={"X-Tenant-Id": "t1", "X-Papel": "admin"}).json()[0]["source_id"] == "fixture"
