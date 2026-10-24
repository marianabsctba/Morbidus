"""audit-svc: log imutável de todas as consultas (LGPD) e detector de abuso sobre esse log."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, HTTPException, Query
from morbidus_common.bus import EventBus, make_bus
from morbidus_common.db import make_engine, utcnow
from morbidus_common.events import QueryPerformed, Topics
from morbidus_common.logging import setup_logging
from morbidus_common.web import TenantContext, create_app, require_admin, require_tenant
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from audit_svc.config import AuditSettings
from audit_svc.alertas import notificar
from audit_svc.models import Alerta, AuditEntry, setup_schema
from audit_svc.sentinela import ROTULOS, avaliar


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
    ip_origem: str | None
    user_agent: str | None


class AlertaOut(BaseModel):
    id: str
    regra: str
    rotulo: str
    severidade: str
    tenant_id: str | None
    ip: str | None
    descricao: str
    evidencias: dict
    criado_em: datetime
    status: str
    resolvido_em: datetime | None


class AlertaIn(BaseModel):
    status: str = Field(pattern="^(aberto|resolvido)$")


def _alerta_out(a: Alerta) -> AlertaOut:
    return AlertaOut(
        id=a.id,
        regra=a.regra,
        rotulo=ROTULOS.get(a.regra, a.regra),
        severidade=a.severidade,
        tenant_id=a.tenant_id,
        ip=a.ip,
        descricao=a.descricao,
        evidencias=a.evidencias or {},
        criado_em=a.criado_em,
        status=a.status,
        resolvido_em=a.resolvido_em,
    )


def build_app(settings: AuditSettings | None = None, bus: EventBus | None = None):
    settings = settings or AuditSettings()
    setup_logging("audit", settings.log_level)
    engine = make_engine(settings.database_url)
    sessions = sessionmaker(engine, expire_on_commit=False)
    bus = bus or make_bus(settings, group_id="audit")

    def _store(event: QueryPerformed) -> list[Alerta]:
        with sessions() as db:
            if db.get(AuditEntry, event.event_id):
                return []
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
                    ip_origem=event.ip_origem,
                    user_agent=event.user_agent,
                    dias_desde_obito=event.dias_desde_obito,
                )
            )
            db.flush()
            novos = avaliar(db, event, settings)
            db.commit()
            return novos

    async def handle(payload: dict) -> None:
        novos = await asyncio.to_thread(_store, QueryPerformed.model_validate(payload))
        if novos:
            await asyncio.to_thread(notificar, settings, novos)

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
        ip: str | None = Query(None, max_length=45, description="Filtra por IP de origem"),
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
            if ip:
                stmt = stmt.where(AuditEntry.ip_origem == ip)
            stmt = stmt.order_by(AuditEntry.ocorrido_em.desc()).limit(limit).offset(offset)
            return db.scalars(stmt).all()

    @app.get("/v1/alertas", response_model=list[AlertaOut])
    def listar_alertas(
        _: TenantContext = Depends(require_admin),
        status: str | None = Query("aberto", pattern="^(aberto|resolvido)$"),
        limit: int = Query(100, ge=1, le=500),
    ):
        """Suspeitas de abuso abertas pelo detector. Só administradores."""
        with sessions() as db:
            stmt = select(Alerta).order_by(Alerta.criado_em.desc()).limit(limit)
            if status:
                stmt = stmt.where(Alerta.status == status)
            return [_alerta_out(a) for a in db.scalars(stmt)]

    @app.patch("/v1/alertas/{alerta_id}", response_model=AlertaOut)
    def alterar_alerta(alerta_id: str, body: AlertaIn, _: TenantContext = Depends(require_admin)):
        with sessions() as db:
            alerta = db.get(Alerta, alerta_id)
            if alerta is None:
                raise HTTPException(status_code=404, detail="alerta não encontrado")
            alerta.status = body.status
            alerta.resolvido_em = utcnow() if body.status == "resolvido" else None
            db.commit()
            return _alerta_out(alerta)

    return app
