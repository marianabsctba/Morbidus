"""query-svc: ponto de consulta DIFP. Junta provedores oficiais e obituários num só veredito."""

import asyncio
import hashlib
import hmac
import logging
from contextlib import asynccontextmanager
from datetime import date
from enum import Enum
from uuid import uuid4

import httpx
from fastapi import Depends, HTTPException
from morbidus_common.bus import EventBus, make_bus
from morbidus_common.events import QueryPerformed, QueryStatus, Topics
from morbidus_common.logging import setup_logging
from morbidus_common.search import DeathIndex, make_index
from morbidus_common.text import is_valid_cpf, mask_cpf, only_digits
from morbidus_common.web import TenantContext, create_app, require_tenant
from pydantic import BaseModel, Field, model_validator

from query_svc.config import QuerySettings
from query_svc.scoring import score_candidate

log = logging.getLogger(__name__)

AVISO_OBITUARIO = (
    "Obituários não trazem CPF: o resultado é um sinal de risco por similaridade. "
    "Confirme em fonte oficial antes de decidir."
)


class Finalidade(str, Enum):
    ONBOARDING = "onboarding"
    CONCESSAO_CREDITO = "concessao_credito"
    PREVENCAO_FRAUDE = "prevencao_fraude"
    PAGAMENTO_BENEFICIO = "pagamento_beneficio"
    SINISTRO_SEGURO = "sinistro_seguro"


class ConsultaIn(BaseModel):
    cpf: str | None = None
    nome: str | None = Field(default=None, max_length=300)
    data_nascimento: date | None = None
    cidade: str | None = Field(default=None, max_length=120)
    uf: str | None = Field(default=None, min_length=2, max_length=2)
    finalidade: Finalidade = Field(description="Base legal da consulta, registrada na auditoria (LGPD).")

    @model_validator(mode="after")
    def _exige_identificador(self):
        if not self.cpf and not self.nome:
            raise ValueError("informe cpf ou nome")
        if self.nome and len(self.nome.split()) < 2:
            raise ValueError("informe nome e sobrenome")
        return self


class Evidencia(BaseModel):
    tipo: str  # oficial | obituario
    fonte: str
    score: float
    detalhes: dict


class ConsultaOut(BaseModel):
    consulta_id: str
    status: QueryStatus
    score: float
    evidencias: list[Evidencia]
    fontes_indisponiveis: list[str]
    aviso: str | None = None


def build_app(
    settings: QuerySettings | None = None,
    bus: EventBus | None = None,
    index: DeathIndex | None = None,
    provider_client: httpx.AsyncClient | None = None,
):
    settings = settings or QuerySettings()
    setup_logging("query", settings.log_level)
    bus = bus or make_bus(settings, group_id="query")
    index = index or make_index(settings.search_backend, settings.opensearch_url)
    client = provider_client or httpx.AsyncClient(
        base_url=settings.provider_url, timeout=settings.provider_timeout_seconds
    )

    @asynccontextmanager
    async def lifespan(app):
        await bus.start()
        yield
        await bus.stop()
        await client.aclose()

    app = create_app("query", "Consulta de identidades falecidas por CPF e nome.", lifespan)

    async def _oficiais(cpf: str) -> tuple[list[Evidencia], list[str]]:
        try:
            resp = await client.post("/v1/lookup", json={"cpf": cpf})
            resp.raise_for_status()
        except httpx.HTTPError:
            log.exception("provider-svc indisponível")
            return [], ["provider-svc"]
        evidencias, indisponiveis = [], []
        for r in resp.json()["resultados"]:
            if r["status"] == "indisponivel":
                indisponiveis.append(r["provider"])
            elif r["status"] == "falecido":
                evidencias.append(Evidencia(tipo="oficial", fonte=r["provider"], score=1.0, detalhes=r))
        return evidencias, indisponiveis

    async def _obituarios(body: ConsultaIn) -> list[Evidencia]:
        candidatos = await asyncio.to_thread(index.search, body.nome, body.uf)
        evidencias = []
        for c in candidatos:
            score, motivos = score_candidate(c, body.nome, body.uf, body.cidade, body.data_nascimento)
            if score >= settings.sinal_fraco_min:
                campos = ("nome", "idade", "data_nascimento", "data_falecimento", "cidade", "uf", "fontes")
                detalhes = {k: c.get(k) for k in campos}
                detalhes["motivos"] = motivos
                evidencias.append(Evidencia(tipo="obituario", fonte=c["record_id"], score=score, detalhes=detalhes))
        return sorted(evidencias, key=lambda e: e.score, reverse=True)

    @app.post("/v1/consultas", response_model=ConsultaOut)
    async def consultar(body: ConsultaIn, tenant: TenantContext = Depends(require_tenant)):
        cpf = only_digits(body.cpf) if body.cpf else None
        if cpf and not is_valid_cpf(cpf):
            raise HTTPException(status_code=422, detail="CPF inválido")

        evidencias: list[Evidencia] = []
        indisponiveis: list[str] = []
        fontes = []
        if cpf:
            fontes.append("oficial")
            oficiais, indisponiveis = await _oficiais(cpf)
            evidencias += oficiais
        if body.nome:
            fontes.append("obituario")
            try:
                evidencias += await _obituarios(body)
            except Exception:
                log.exception("índice de obituários indisponível")
                indisponiveis.append("obituario")

        if not tenant.admin:
            # De onde veio cada registro é informação interna da base.
            for e in evidencias:
                e.detalhes.pop("fontes", None)

        score = max((e.score for e in evidencias), default=0.0)
        if any(e.tipo == "oficial" for e in evidencias):
            status = QueryStatus.OBITO_CONFIRMADO
        elif score >= settings.sinal_forte_min:
            status = QueryStatus.SINAL_FORTE
        elif score >= settings.sinal_fraco_min:
            status = QueryStatus.SINAL_FRACO
        else:
            status = QueryStatus.SEM_REGISTRO

        consulta_id = uuid4().hex
        await bus.publish(
            Topics.QUERY_PERFORMED,
            QueryPerformed(
                query_id=consulta_id,
                tenant_id=tenant.tenant_id,
                api_key_id=tenant.api_key_id,
                finalidade=body.finalidade.value,
                cpf_mascarado=mask_cpf(cpf) if cpf else None,
                cpf_hash=hmac.new(settings.audit_cpf_salt.encode(), cpf.encode(), hashlib.sha256).hexdigest()
                if cpf
                else None,
                nome_consultado=body.nome,
                status=status,
                score=score,
                fontes_consultadas=fontes,
            ),
            key=tenant.tenant_id,
        )
        tem_obituario = any(e.tipo == "obituario" for e in evidencias)
        return ConsultaOut(
            consulta_id=consulta_id,
            status=status,
            score=score,
            evidencias=evidencias,
            fontes_indisponiveis=indisponiveis,
            aviso=AVISO_OBITUARIO if tem_obituario and status != QueryStatus.OBITO_CONFIRMADO else None,
        )

    return app
