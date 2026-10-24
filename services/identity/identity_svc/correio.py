"""Envio de e-mail de confirmação de cadastro.

Teste manual de configuração (dentro do container):
    python -m identity_svc.correio destino@exemplo.com
"""

import logging
import smtplib
import sys
from email.message import EmailMessage
from email.utils import make_msgid

from identity_svc.config import IdentitySettings

log = logging.getLogger(__name__)


def _mensagem(settings: IdentitySettings, para: str, assunto: str, texto: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = settings.smtp_from
    msg["To"] = para
    msg["Message-ID"] = make_msgid(domain=settings.smtp_from.rsplit("@", 1)[-1].strip(">"))
    msg.set_content(texto)
    return msg


def _enviar(settings: IdentitySettings, msg: EmailMessage) -> None:
    # Porta 465 usa SSL direto; as demais negociam STARTTLS.
    if settings.smtp_ssl or settings.smtp_port == 465:
        conexao = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20)
    else:
        conexao = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
        conexao.starttls()
    with conexao as smtp:
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)


def envia_confirmacao(settings: IdentitySettings, para: str, nome: str, token: str) -> None:
    link = f"{settings.public_url.rstrip('/')}/verificar?token={token}"
    texto = (
        f"Olá, {nome}.\n\n"
        f"Para ativar sua conta no MORBiDus, abra o link abaixo nas próximas 24 horas:\n\n{link}\n\n"
        "Se você não pediu este cadastro, ignore este e-mail.\n\n"
        "MORBiDus · Death Identity Fraud Prevention"
    )
    try:
        _enviar(settings, _mensagem(settings, para, "Confirme seu cadastro no MORBiDus", texto))
    except Exception:
        log.exception("falha ao enviar e-mail de confirmação")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("uso: python -m identity_svc.correio destino@exemplo.com")
    config = IdentitySettings()
    if not config.smtp_host:
        sys.exit("SMTP_HOST não configurado")
    _enviar(
        config,
        _mensagem(config, sys.argv[1], "Teste do MORBiDus", "Se você recebeu este e-mail, o SMTP está funcionando."),
    )
    print(f"e-mail de teste enviado para {sys.argv[1]} via {config.smtp_host}:{config.smtp_port}")
