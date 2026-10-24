"""Detector de abuso: avalia regras a cada consulta registrada e abre alertas.

As regras olham só a trilha de auditoria (contagens em janelas de tempo), nunca
o conteúdo do registro de óbito.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from morbidus_common.events import QueryPerformed, QueryStatus
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from audit_svc.config import AuditSettings
from audit_svc.models import Alerta, AuditEntry

ACERTOS = (QueryStatus.OBITO_CONFIRMADO.value, QueryStatus.SINAL_FORTE.value)

ROTULOS = {
    "rajada": "Rajada de consultas",
    "varredura_nomes": "Varredura de nomes",
    "obitos_recentes": "Caça a óbitos recentes",
    "taxa_acerto": "Taxa de acerto anômala",
    "ip_multicontas": "Várias contas no mesmo IP",
}


@dataclass
class Achado:
    regra: str
    severidade: str
    descricao: str
    evidencias: dict
    tenant_id: str | None = None
    ip: str | None = None


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _regras(db: Session, ev: QueryPerformed, cfg: AuditSettings) -> list[Achado]:
    agora = _aware(ev.occurred_at)
    da_conta = AuditEntry.tenant_id == ev.tenant_id

    def desde(**delta):
        return AuditEntry.ocorrido_em >= agora - timedelta(**delta)

    achados = []

    n = db.scalar(select(func.count()).select_from(AuditEntry).where(da_conta, desde(minutes=10)))
    if n >= cfg.rajada_limite:
        achados.append(Achado("rajada", "alta", f"{n} consultas em 10 minutos", {"consultas_10min": n}, ev.tenant_id))

    n = db.scalar(
        select(func.count(func.distinct(AuditEntry.nome_consultado))).where(
            da_conta, desde(hours=1), AuditEntry.nome_consultado.is_not(None)
        )
    )
    if n >= cfg.varredura_limite:
        achados.append(
            Achado("varredura_nomes", "alta", f"{n} nomes diferentes consultados em 1 hora", {"nomes_1h": n}, ev.tenant_id)
        )

    n = db.scalar(
        select(func.count())
        .select_from(AuditEntry)
        .where(
            da_conta,
            desde(hours=24),
            AuditEntry.status.in_(ACERTOS),
            AuditEntry.dias_desde_obito <= cfg.obito_recente_dias,
        )
    )
    if n >= cfg.obitos_recentes_limite:
        achados.append(
            Achado(
                "obitos_recentes",
                "alta",
                f"{n} acertos em óbitos de até {cfg.obito_recente_dias} dias nas últimas 24 horas",
                {"acertos_recentes_24h": n},
                ev.tenant_id,
            )
        )

    total, acertos = db.execute(
        select(func.count(), func.sum(case((AuditEntry.status.in_(ACERTOS), 1), else_=0))).where(da_conta, desde(hours=24))
    ).one()
    acertos = acertos or 0
    if total >= cfg.taxa_minimo_consultas and acertos / total >= cfg.taxa_acerto_limite:
        pct = round(100 * acertos / total)
        achados.append(
            Achado(
                "taxa_acerto",
                "media",
                f"{pct}% de acertos em {total} consultas nas últimas 24 horas",
                {"consultas_24h": total, "acertos_24h": acertos},
                ev.tenant_id,
            )
        )

    if ev.ip_origem:
        n = db.scalar(
            select(func.count(func.distinct(AuditEntry.tenant_id))).where(
                AuditEntry.ip_origem == ev.ip_origem, desde(hours=24)
            )
        )
        if n >= cfg.ip_contas_limite:
            achados.append(
                Achado(
                    "ip_multicontas",
                    "alta",
                    f"{n} contas diferentes consultando do mesmo IP em 24 horas",
                    {"contas_24h": n},
                    ip=ev.ip_origem,
                )
            )
    return achados


def avaliar(db: Session, ev: QueryPerformed, cfg: AuditSettings) -> list[Alerta]:
    """Abre alertas novos. O mesmo alerta (regra e alvo) não se repete enquanto
    houver um aberto das últimas horas, para não lotar a caixa de ninguém."""
    novos = []
    limite_repeticao = _aware(ev.occurred_at) - timedelta(hours=cfg.alerta_silencio_horas)
    for achado in _regras(db, ev, cfg):
        alvo = (Alerta.ip == achado.ip) if achado.ip else (Alerta.tenant_id == achado.tenant_id)
        repetido = db.scalar(
            select(Alerta.id).where(
                Alerta.regra == achado.regra, alvo, Alerta.status == "aberto", Alerta.criado_em >= limite_repeticao
            )
        )
        if repetido:
            continue
        alerta = Alerta(
            regra=achado.regra,
            severidade=achado.severidade,
            tenant_id=achado.tenant_id,
            ip=achado.ip,
            descricao=achado.descricao,
            evidencias=achado.evidencias,
            criado_em=ev.occurred_at,
        )
        db.add(alerta)
        novos.append(alerta)
    return novos
