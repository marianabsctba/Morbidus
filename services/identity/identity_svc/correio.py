"""E-mail de confirmação de cadastro.

Teste manual de configuração (dentro do container):
    python -m identity_svc.correio destino@exemplo.com
"""

import logging
import sys

from morbidus_common import correio as comum
from morbidus_common.correio import mensagem

from identity_svc.config import IdentitySettings

log = logging.getLogger(__name__)

# Mantido como atributo do módulo para os testes poderem trocar o envio.
smtplib = comum.smtplib


def envia_confirmacao(settings: IdentitySettings, para: str, nome: str, token: str) -> None:
    link = f"{settings.public_url.rstrip('/')}/verificar?token={token}"
    texto = (
        f"Olá, {nome}.\n\n"
        f"Para ativar sua conta no MORBiDus, abra o link abaixo nas próximas 24 horas:\n\n{link}\n\n"
        "Se você não pediu este cadastro, ignore este e-mail.\n\n"
        "MORBiDus · Death Identity Fraud Prevention"
    )
    try:
        comum.enviar(settings, mensagem(settings, para, "Confirme seu cadastro no MORBiDus", texto))
    except Exception:
        log.exception("falha ao enviar e-mail de confirmação")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("uso: python -m identity_svc.correio destino@exemplo.com")
    config = IdentitySettings()
    if not config.smtp_host:
        sys.exit("SMTP_HOST não configurado")
    comum.enviar(
        config,
        mensagem(config, sys.argv[1], "Teste do MORBiDus", "Se você recebeu este e-mail, o SMTP está funcionando."),
    )
    print(f"e-mail de teste enviado para {sys.argv[1]} via {config.smtp_host}:{config.smtp_port}")
