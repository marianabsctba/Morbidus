"""audit-svc: log imutável de todas as consultas (LGPD) e detector de abuso sobre esse log."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import base64
import hmac
import logging

from fastapi import Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from morbidus_common.bus import EventBus, make_bus
from morbidus_common.db import make_engine, utcnow
from morbidus_common.events import QueryPerformed, Topics
from morbidus_common.logging import setup_logging
from morbidus_common.web import TenantContext, create_app, require_admin, require_tenant
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from audit_svc.config import AuditSettings
from audit_svc import cti
from audit_svc.alertas import avisar_instituicoes, notificar
from audit_svc.models import Alerta, AuditEntry, IdentidadeConsultada, aplicar_retencao, setup_schema
from audit_svc.sentinela import ROTULOS, avaliar


log = logging.getLogger(__name__)


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
    # "confirmado" = abuso confirmado pela administração; só esses vão para o feed de CTI.
    status: str = Field(pattern="^(aberto|resolvido|confirmado)$")


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
            for chave in event.identidades:
                db.add(
                    IdentidadeConsultada(
                        query_id=event.query_id, chave=chave, tenant_id=event.tenant_id, ocorrido_em=event.occurred_at
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
            for alerta in novos:
                if alerta.regra == "identidade_quente":
                    consultas = await asyncio.to_thread(_consultas_da_chave, alerta.chave, alerta.criado_em)
                    await asyncio.to_thread(avisar_instituicoes, settings, consultas)

    def _consultas_da_chave(chave: str, ate: datetime) -> list[tuple[str, str, datetime]]:
        inicio = ate - timedelta(days=settings.calor_janela_dias)
        with sessions() as db:
            linhas = db.execute(
                select(IdentidadeConsultada.tenant_id, IdentidadeConsultada.query_id, IdentidadeConsultada.ocorrido_em)
                .where(IdentidadeConsultada.chave == chave, IdentidadeConsultada.ocorrido_em >= inicio)
                .order_by(IdentidadeConsultada.ocorrido_em)
            ).all()
        return [tuple(linha) for linha in linhas]

    bus.subscribe(Topics.QUERY_PERFORMED, handle)

    def _reter() -> None:
        try:
            apagados = aplicar_retencao(engine, settings.auditoria_retencao_dias)
            if any(apagados.values()):
                log.info("retenção da auditoria: %s", apagados)
        except Exception:
            log.exception("falha na rotina de retenção da auditoria")

    async def _retencao_diaria() -> None:
        while True:
            await asyncio.sleep(24 * 3600)
            await asyncio.to_thread(_reter)

    @asynccontextmanager
    async def lifespan(app):
        setup_schema(engine)
        # Primeira rodada antes de consumir eventos: sem disputa pela conexão na partida.
        _reter()
        await bus.start()
        retencao = asyncio.create_task(_retencao_diaria())
        yield
        retencao.cancel()
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

    @app.get("/interno/calor", include_in_schema=False)
    def calor(tenant: str, chave: list[str] = Query(default=[])) -> dict[str, int]:
        """Para o query-svc: quantas OUTRAS instituições bateram em cada identidade na janela.
        Rota interna: o gateway não a expõe."""
        inicio = utcnow() - timedelta(days=settings.calor_janela_dias)
        with sessions() as db:
            return {
                c: db.scalar(
                    select(func.count(func.distinct(IdentidadeConsultada.tenant_id))).where(
                        IdentidadeConsultada.chave == c,
                        IdentidadeConsultada.tenant_id != tenant,
                        IdentidadeConsultada.ocorrido_em >= inicio,
                    )
                )
                for c in chave[:20]
            }

    @app.get("/v1/alertas", response_model=list[AlertaOut])
    def listar_alertas(
        _: TenantContext = Depends(require_admin),
        status: str | None = Query("aberto", pattern="^(aberto|resolvido|confirmado)$"),
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
            alerta.resolvido_em = utcnow() if body.status in ("resolvido", "confirmado") else None
            db.commit()
            return _alerta_out(alerta)

    # ---------- Inteligência de ameaças (STIX 2.1 / TAXII 2.1) ----------

    @app.get("/v1/cti/stix")
    def baixar_stix(_: TenantContext = Depends(require_admin)):
        """Pacote STIX 2.1 com os IPs de alertas confirmados. Só administradoras."""
        with sessions() as db:
            return JSONResponse(
                cti.pacote(db),
                media_type=cti.MEDIA_STIX,
                headers={"Content-Disposition": 'attachment; filename="morbidus-cti.json"'},
            )

    tokens_taxii = [t.strip() for t in settings.cti_taxii_tokens.split(",") if t.strip()]

    def autorizar_taxii(authorization: str | None = Header(default=None)) -> None:
        """Aceita Bearer <token> ou Basic com o token como senha (formato de MISP e OpenCTI)."""
        if not tokens_taxii:
            raise HTTPException(status_code=404, detail="feed TAXII desativado")
        enviado = ""
        if authorization and authorization.lower().startswith("bearer "):
            enviado = authorization[7:].strip()
        elif authorization and authorization.lower().startswith("basic "):
            try:
                enviado = base64.b64decode(authorization[6:]).decode().split(":", 1)[-1]
            except ValueError:
                enviado = ""
        if not any(hmac.compare_digest(enviado, t) for t in tokens_taxii):
            raise HTTPException(
                status_code=401, detail="token inválido", headers={"WWW-Authenticate": 'Bearer realm="taxii"'}
            )

    def _taxii(dados: dict) -> JSONResponse:
        return JSONResponse(dados, media_type=cti.MEDIA_TAXII)

    raiz = f"{settings.public_url.rstrip('/')}/taxii2/morbidus/"
    colecao = {
        "id": cti.COLECAO,
        "title": "MORBiDus: IPs com abuso confirmado",
        "description": "Origens de consultas abusivas a identidades de pessoas falecidas. TLP:AMBER.",
        "can_read": True,
        "can_write": False,
        "media_types": [cti.MEDIA_STIX],
    }
    taxii = [Depends(autorizar_taxii)]

    @app.get("/taxii2/", dependencies=taxii, include_in_schema=False)
    def taxii_descoberta():
        return _taxii({"title": "MORBiDus TAXII", "default": raiz, "api_roots": [raiz]})

    @app.get("/taxii2/morbidus/", dependencies=taxii, include_in_schema=False)
    def taxii_raiz():
        return _taxii({"title": "MORBiDus", "versions": [cti.MEDIA_TAXII], "max_content_length": 10_485_760})

    @app.get("/taxii2/morbidus/collections/", dependencies=taxii, include_in_schema=False)
    def taxii_colecoes():
        return _taxii({"collections": [colecao]})

    @app.get("/taxii2/morbidus/collections/{colecao_id}/", dependencies=taxii, include_in_schema=False)
    def taxii_colecao(colecao_id: str):
        if colecao_id != cti.COLECAO:
            raise HTTPException(status_code=404, detail="coleção não encontrada")
        return _taxii(colecao)

    @app.get("/taxii2/morbidus/collections/{colecao_id}/objects/", dependencies=taxii, include_in_schema=False)
    def taxii_objetos(colecao_id: str, added_after: datetime | None = None):
        if colecao_id != cti.COLECAO:
            raise HTTPException(status_code=404, detail="coleção não encontrada")
        with sessions() as db:
            objetos = cti.produtor_e_marcacao() + cti.objetos(db, depois_de=added_after)
        return _taxii({"more": False, "objects": objetos})

    return app
