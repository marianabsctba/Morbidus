"""Envio de e-mail por SMTP, compartilhado entre os serviços."""

import smtplib
from email.message import EmailMessage
from email.utils import make_msgid

from morbidus_common.settings import SmtpSettings


def mensagem(settings: SmtpSettings, para: str | list[str], assunto: str, texto: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = settings.smtp_from
    msg["To"] = para if isinstance(para, str) else ", ".join(para)
    msg["Message-ID"] = make_msgid(domain=settings.smtp_from.rsplit("@", 1)[-1].strip(">"))
    msg.set_content(texto)
    return msg


def enviar(settings: SmtpSettings, msg: EmailMessage) -> None:
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
