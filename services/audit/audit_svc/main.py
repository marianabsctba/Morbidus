"""audit-svc: log imutável de todas as consultas, para prestação de contas na LGPD."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, Query
from morbidus_common.bus import EventBus, make_bus
from morbidus_common.db import make_engine
from morbidus_common.events import QueryPerformed, Topics
from morbidus_common.logging import setup_logging
from morbidus_common.web import TenantContext, create_app, require_admin, require_tenant
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from audit_svc.config import AuditSettings
from audit_svc.models import AuditEntry, setup_schema


class AuditEntryOut(BaseModel):
    query_id: str
    api_key_id: str | None
    finalidade: str
    cpf_mascarado: str | None
    nome_consultado: str | None
    status: str
    score: float
    fontes_consultadas: list[str]
    ocorrido_em: datetime


class AuditEntryGeralOut(AuditEntryOut):
    tenant_id: str


def build_app(settings: AuditSettings | None = None, bus: EventBus | None = None):
    settings = settings or AuditSettings()
    setup_logging("audit", settings.log_level)
    engine = make_engine(settings.database_url)
    sessions = sessionmaker(engine, expire_on_commit=False)
    bus = bus or make_bus(settings, group_id="audit")

    def _store(event: QueryPerformed) -> None:
        with sessions() as db:
            if db.get(AuditEntry, event.event_id):
                return
            db.add(
                AuditEntry(
                    event_id=event.event_id,
                    query_id=event.query_id,
                    tenant_id=event.tenant_id,
                    api_key_id=event.api_key_id,
                    finalidade=event.finalidade,
                    cpf_mascarado=event.cpf_mascarado,
                    cpf_hash=event.cpf_hash,
                    nome_consultado=event.nome_consultado,
                    status=event.status.value,
                    score=event.score,
                    fontes_consultadas=event.fontes_consultadas,
                    ocorrido_em=event.occurred_at,
                )
            )
            db.commit()

    async def handle(payload: dict) -> None:
        await asyncio.to_thread(_store, QueryPerformed.model_validate(payload))

    bus.subscribe(Topics.QUERY_PERFORMED, handle)

    @asynccontextmanager
    async def lifespan(app):
        setup_schema(engine)
        await bus.start()
        yield
        await bus.stop()
        engine.dispose()

    app = create_app("audit", "Trilha de auditoria das consultas.", lifespan)

    @app.get("/v1/auditoria", response_model=list[AuditEntryOut])
    def listar(
        tenant: TenantContext = Depends(require_tenant),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        with sessions() as db:
            stmt = (
                select(AuditEntry)
                .where(AuditEntry.tenant_id == tenant.tenant_id)
                .order_by(AuditEntry.ocorrido_em.desc())
                .limit(limit)
                .offset(offset)
            )
            return db.scalars(stmt).all()

    @app.get("/v1/auditoria/geral", response_model=list[AuditEntryGeralOut])
    def listar_geral(
        _: TenantContext = Depends(require_admin),
        tenant_id: str | None = Query(None, description="Filtra por uma conta"),
        status: str | None = Query(None),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        """Todas as consultas de todas as contas. Só administradores."""
        with sessions() as db:
            stmt = select(AuditEntry)
            if tenant_id:
                stmt = stmt.where(AuditEntry.tenant_id == tenant_id)
            if status:
                stmt = stmt.where(AuditEntry.status == status)
            stmt = stmt.order_by(AuditEntry.ocorrido_em.desc()).limit(limit).offset(offset)
            return db.scalars(stmt).all()

    return app
