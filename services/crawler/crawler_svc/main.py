"""crawler-svc: coleta obituários das capitais e publica entradas brutas no Kafka."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import HTTPException
from morbidus_common.bus import EventBus, make_bus
from morbidus_common.logging import setup_logging
from morbidus_common.web import create_app

from crawler_svc.config import CrawlerSettings
from crawler_svc.fetcher import PoliteFetcher
from crawler_svc.rawstore import MemoryRawStore, MinioRawStore, RawStore
from crawler_svc.runner import run_spider
from crawler_svc.spiders import SPIDERS

log = logging.getLogger(__name__)


def _make_store(settings: CrawlerSettings) -> RawStore:
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
    unknown = set(enabled) - SPIDERS.keys()
    if unknown:
        raise ValueError(f"spiders desconhecidos: {sorted(unknown)}")
    spiders = {name: SPIDERS[name]() for name in enabled}

    async def _run(name: str) -> int:
        fetcher = PoliteFetcher(settings.user_agent, settings.request_delay_seconds)
        try:
            return await run_spider(spiders[name], fetcher, store, bus)
        finally:
            await fetcher.aclose()

    async def _scheduler() -> None:
        while True:
            for name in spiders:
                try:
                    await _run(name)
                except Exception:
                    log.exception("coleta agendada falhou: %s", name)
            await asyncio.sleep(settings.crawl_interval_minutes * 60)

    @asynccontextmanager
    async def lifespan(app):
        await bus.start()
        task = asyncio.create_task(_scheduler()) if settings.crawl_interval_minutes > 0 else None
        yield
        if task:
            task.cancel()
        await bus.stop()

    app = create_app("crawler", "Coleta de obituários de jornais e serviços funerários.", lifespan)

    @app.get("/v1/sources")
    def list_sources():
        return [{"source_id": n, "cidade": s.cidade, "uf": s.uf} for n, s in spiders.items()]

    @app.post("/v1/sources/{source_id}/run")
    async def run_source(source_id: str):
        if source_id not in spiders:
            raise HTTPException(status_code=404, detail="fonte não habilitada")
        return {"source_id": source_id, "entradas_publicadas": await _run(source_id)}

    return app
