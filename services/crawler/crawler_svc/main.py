"""crawler-svc: coleta obituários das capitais e publica entradas brutas no Kafka."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import HTTPException, Query
from morbidus_common.bus import EventBus, make_bus
from morbidus_common.logging import setup_logging
from morbidus_common.web import create_app

from crawler_svc.config import CrawlerSettings
from crawler_svc.fetcher import PoliteFetcher
from crawler_svc.rawstore import FileRawStore, MemoryRawStore, MinioRawStore, RawStore
from crawler_svc.runner import run_spider
from crawler_svc.spiders import SPIDERS

log = logging.getLogger(__name__)


def _make_store(settings: CrawlerSettings) -> RawStore:
    if settings.raw_store_backend == "file":
        return FileRawStore(settings.raw_store_dir)
    if settings.raw_store_backend == "minio":
        return MinioRawStore(
            settings.minio_endpoint,
            settings.minio_access_key,
            settings.minio_secret_key,
            settings.minio_bucket,
            settings.minio_secure,
        )
    return MemoryRawStore()


def build_app(
    settings: CrawlerSettings | None = None,
    bus: EventBus | None = None,
    store: RawStore | None = None,
):
    settings = settings or CrawlerSettings()
    setup_logging("crawler", settings.log_level)
    bus = bus or make_bus(settings, group_id="crawler")
    store = store or _make_store(settings)
    enabled = [s.strip() for s in settings.enabled_spiders.split(",") if s.strip()]
    if enabled == ["all"]:
        enabled = [s for s in SPIDERS if s != "fixture"]
    unknown = set(enabled) - SPIDERS.keys()
    if unknown:
        raise ValueError(f"spiders desconhecidos: {sorted(unknown)}")
    spiders = {name: SPIDERS[name]() for name in enabled}
    runs: dict[str, dict] = {}
    tasks: set[asyncio.Task] = set()

    async def _run(name: str, backfill: bool = False, max_pages: int | None = None) -> int:
        runs[name] = {"status": "rodando", "backfill": backfill, "inicio": datetime.now(timezone.utc).isoformat()}
        fetcher = PoliteFetcher(settings.user_agent, settings.request_delay_seconds)
        try:
            total = await run_spider(spiders[name], fetcher, store, bus, backfill=backfill, max_pages=max_pages)
        except Exception as exc:
            log.exception("coleta falhou: %s", name)
            runs[name].update(status="erro", erro=repr(exc), fim=datetime.now(timezone.utc).isoformat())
            raise
        finally:
            await fetcher.aclose()
        runs[name].update(status="ok", entradas_publicadas=total, fim=datetime.now(timezone.utc).isoformat())
        return total

    def _em_segundo_plano(coro) -> None:
        task = asyncio.create_task(coro)
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    async def _todas(backfill: bool, max_pages: int | None) -> None:
        # Cada fonte tem seu próprio host e ritmo, então rodam em paralelo.
        await asyncio.gather(*(_run(n, backfill, max_pages) for n in spiders), return_exceptions=True)

    async def _scheduler() -> None:
        while True:
            await _todas(backfill=False, max_pages=None)
            await asyncio.sleep(settings.crawl_interval_minutes * 60)

    @asynccontextmanager
    async def lifespan(app):
        await bus.start()
        if settings.crawl_interval_minutes > 0:
            _em_segundo_plano(_scheduler())
        yield
        for task in list(tasks):
            task.cancel()
        await bus.stop()

    app = create_app("crawler", "Coleta de obituários de jornais, cemitérios e serviços funerários.", lifespan)

    @app.get("/v1/sources")
    def list_sources():
        return [
            {"source_id": n, "cidade": s.cidade, "uf": s.uf, "descricao": s.descricao, "ultima_coleta": runs.get(n)}
            for n, s in spiders.items()
        ]

    @app.post("/v1/sources/{source_id}/run")
    async def run_source(source_id: str):
        if source_id not in spiders:
            raise HTTPException(status_code=404, detail="fonte não habilitada")
        return {"source_id": source_id, "entradas_publicadas": await _run(source_id)}

    @app.post("/v1/backfill", status_code=202)
    async def backfill(
        source_id: str | None = None,
        max_pages: int | None = Query(default=None, ge=1, description="Limite de páginas por fonte"),
    ):
        """Percorre o histórico das fontes em segundo plano. Acompanhe em GET /v1/sources."""
        if source_id:
            if source_id not in spiders:
                raise HTTPException(status_code=404, detail="fonte não habilitada")
            _em_segundo_plano(_run(source_id, backfill=True, max_pages=max_pages))
            return {"iniciado": [source_id]}
        _em_segundo_plano(_todas(backfill=True, max_pages=max_pages))
        return {"iniciado": list(spiders)}

    return app
