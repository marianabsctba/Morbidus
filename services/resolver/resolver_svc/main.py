"""resolver-svc: consome obituary.raw, deduplica, grava no Postgres e indexa no OpenSearch."""

import asyncio
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, HTTPException
from morbidus_common.bus import EventBus, make_bus
from morbidus_common.db import ensure_columns, make_engine
from morbidus_common.events import DeathRecordNormalized, Topics
from morbidus_common.logging import setup_logging
from morbidus_common.search import DeathIndex, make_index
from morbidus_common.web import TenantContext, create_app, require_admin
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from resolver_svc.config import ResolverSettings
from resolver_svc.canarios import plantar
from resolver_svc.models import Base, DeathRecord
from resolver_svc.resolver import Resolver, to_event


class CanarioOut(BaseModel):
    nome: str
    cidade: str
    uf: str
    data_nascimento: date | None
    data_falecimento: date | None


class PlantarIn(BaseModel):
    quantidade: int = Field(default=10, ge=1, le=50)


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
        ensure_columns(engine, "death_records", {"canario": "BOOLEAN DEFAULT FALSE"})
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
            reais = DeathRecord.canario.is_not(True)
            total = db.scalar(select(func.count()).select_from(DeathRecord).where(reais))
            por_uf = db.execute(
                select(DeathRecord.uf, DeathRecord.cidade, func.count())
                .where(reais)
                .group_by(DeathRecord.uf, DeathRecord.cidade)
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

    @app.get("/v1/canarios", response_model=list[CanarioOut])
    def listar_canarios(_: TenantContext = Depends(require_admin)):
        """Só administradoras: são os nomes a procurar em vazamentos e fraudes."""
        with sessions() as db:
            return db.scalars(
                select(DeathRecord).where(DeathRecord.canario.is_(True)).order_by(DeathRecord.criado_em.desc())
            ).all()

    @app.post("/v1/canarios", response_model=list[CanarioOut], status_code=201)
    def plantar_canarios(body: PlantarIn, _: TenantContext = Depends(require_admin)):
        with sessions() as db:
            return [
                CanarioOut(
                    nome=c.nome, cidade=c.cidade, uf=c.uf, data_nascimento=c.data_nascimento, data_falecimento=c.data_falecimento
                )
                for c in plantar(db, index, body.quantidade)
            ]

    @app.get("/v1/records/{record_id}", response_model=DeathRecordNormalized)
    def get_record(record_id: str):
        with sessions() as db:
            rec = db.get(DeathRecord, record_id)
            if not rec:
                raise HTTPException(status_code=404, detail="registro não encontrado")
            return to_event(rec)

    return app
