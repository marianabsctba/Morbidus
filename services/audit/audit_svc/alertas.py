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
        alvo = f"IP {alerta.ip}" if alerta.ip else f"conta {alerta.tenant_id}"
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
