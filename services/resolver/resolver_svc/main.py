"""resolver-svc: consome obituary.raw, deduplica, grava no Postgres e indexa no OpenSearch."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import HTTPException
from morbidus_common.bus import EventBus, make_bus
from morbidus_common.db import make_engine
from morbidus_common.events import DeathRecordNormalized, Topics
from morbidus_common.logging import setup_logging
from morbidus_common.search import DeathIndex, make_index
from morbidus_common.web import create_app
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from resolver_svc.config import ResolverSettings
from resolver_svc.models import Base, DeathRecord
from resolver_svc.resolver import Resolver, to_event


def build_app(
    settings: ResolverSettings | None = None,
    bus: EventBus | None = None,
    index: DeathIndex | None = None,
):
    settings = settings or ResolverSettings()
    setup_logging("resolver", settings.log_level)
    engine = make_engine(settings.database_url)
    sessions = sessionmaker(engine, expire_on_commit=False)
    bus = bus or make_bus(settings, group_id="resolver")
    index = index or make_index(settings.search_backend, settings.opensearch_url)
    resolver = Resolver(sessions, index, bus, settings.dedup_window_days)
    bus.subscribe(Topics.OBITUARY_RAW, resolver.handle_obituary)

    @asynccontextmanager
    async def lifespan(app):
        Base.metadata.create_all(engine)
        await asyncio.to_thread(index.ensure_index)
        await bus.start()
        yield
        await bus.stop()
        engine.dispose()

    app = create_app("resolver", "Normalização e deduplicação de registros de óbito.", lifespan)
    app.state.resolver = resolver

    @app.get("/v1/estatisticas")
    def estatisticas():
        """Números agregados da base, sem nenhum dado pessoal. Usado pelo painel."""
        with sessions() as db:
            total = db.scalar(select(func.count()).select_from(DeathRecord))
            por_uf = db.execute(
                select(DeathRecord.uf, DeathRecord.cidade, func.count()).group_by(DeathRecord.uf, DeathRecord.cidade)
            ).all()
            ultima = db.scalar(select(func.max(DeathRecord.atualizado_em)))
        ufs: dict[str, dict] = {}
        for uf, cidade, n in por_uf:
            item = ufs.setdefault(uf, {"uf": uf, "total": 0, "cidades": {}})
            item["total"] += n
            item["cidades"][cidade] = n
        return {
            "total": total,
            "por_uf": sorted(ufs.values(), key=lambda x: x["total"], reverse=True),
            "atualizado_em": ultima,
        }

    @app.get("/v1/records/{record_id}", response_model=DeathRecordNormalized)
    def get_record(record_id: str):
        with sessions() as db:
            rec = db.get(DeathRecord, record_id)
            if not rec:
                raise HTTPException(status_code=404, detail="registro não encontrado")
            return to_event(rec)

    return app
