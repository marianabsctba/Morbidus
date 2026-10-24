"""Avisa as administradoras por e-mail quando o detector abre um alerta."""

import json
import logging
import urllib.request

from morbidus_common.correio import enviar, mensagem

from audit_svc.config import AuditSettings
from audit_svc.models import Alerta
from audit_svc.sentinela import ROTULOS

log = logging.getLogger(__name__)


def emails_das_admins(settings: AuditSettings) -> list[str]:
    # Rota interna do identity-svc: o gateway não a expõe.
    with urllib.request.urlopen(f"{settings.identity_url}/interno/admins", timeout=10) as resp:
        return json.load(resp)


def notificar(settings: AuditSettings, alertas: list[Alerta]) -> None:
    if not alertas or not settings.smtp_host:
        return
    try:
        destinos = emails_das_admins(settings)
    except Exception:
        log.exception("não foi possível obter os e-mails das administradoras")
        return
    if not destinos:
        return
    painel = f"{settings.public_url.rstrip('/')}/admin"
    for alerta in alertas:
        rotulo = ROTULOS.get(alerta.regra, alerta.regra)
        if alerta.chave:
            alvo = "identidade de pessoa falecida (as instituições que consultaram também foram avisadas)"
        elif alerta.tenant_id:
            alvo = f"conta {alerta.tenant_id}" + (f", IP {alerta.ip}" if alerta.ip else "")
        else:
            alvo = f"IP {alerta.ip}"
        texto = (
            f"O detector de abuso do MORBiDus abriu um alerta de severidade {alerta.severidade}.\n\n"
            f"{rotulo}: {alerta.descricao}\n"
            f"Alvo: {alvo}\n\n"
            f"Veja as consultas e decida se bloqueia a conta em:\n{painel}\n\n"
            "MORBiDus · Death Identity Fraud Prevention"
        )
        try:
            enviar(settings, mensagem(settings, destinos, f"[MORBiDus] Alerta: {rotulo}", texto))
        except Exception:
            log.exception("falha ao enviar alerta por e-mail")


def emails_por_tenant(settings: AuditSettings, tenants: list[str]) -> dict[str, str]:
    dados = json.dumps(sorted(set(tenants))).encode()
    pedido = urllib.request.Request(
        f"{settings.identity_url}/interno/emails", data=dados, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(pedido, timeout=10) as resp:
        return json.load(resp)


def avisar_instituicoes(settings: AuditSettings, consultas: list[tuple[str, str, object]]) -> None:
    """Avisa quem consultou uma identidade que ficou quente. Sem dado da pessoa no e-mail:
    só o número do laudo e a data, que a própria instituição reconhece na auditoria dela."""
    if not consultas or not settings.smtp_host:
        return
    try:
        emails = emails_por_tenant(settings, [t for t, _, _ in consultas])
    except Exception:
        log.exception("não foi possível obter os e-mails das instituições")
        return
    por_tenant: dict[str, list[str]] = {}
    for tenant, query_id, quando in consultas:
        data = quando.strftime("%d/%m/%Y") if hasattr(quando, "strftime") else str(quando)[:10]
        por_tenant.setdefault(tenant, []).append(f"laudo {query_id[:12]} ({data})")
    outras = len(por_tenant)
    for tenant, laudos in por_tenant.items():
        destino = emails.get(tenant)
        if not destino:
            continue
        texto = (
            "Uma identidade de pessoa falecida que você consultou no MORBiDus está sendo consultada por "
            f"{outras} instituições diferentes nos últimos {settings.calor_janela_dias} dias.\n\n"
            "Isso costuma indicar uma campanha de fraude em andamento usando a mesma identidade.\n\n"
            f"Sua consulta: {', '.join(laudos)}. Veja os detalhes na sua auditoria:\n"
            f"{settings.public_url.rstrip('/')}/auditoria\n\n"
            "MORBiDus · Death Identity Fraud Prevention"
        )
        try:
            enviar(settings, mensagem(settings, destino, "[MORBiDus] Identidade quente: atenção a possível fraude", texto))
        except Exception:
            log.exception("falha ao avisar instituição sobre identidade quente")
