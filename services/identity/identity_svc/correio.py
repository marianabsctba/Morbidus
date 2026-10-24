import logging
import smtplib
from email.message import EmailMessage

from identity_svc.config import IdentitySettings

log = logging.getLogger(__name__)


def envia_confirmacao(settings: IdentitySettings, para: str, nome: str, token: str) -> None:
    link = f"{settings.public_url.rstrip('/')}/verificar?token={token}"
    msg = EmailMessage()
    msg["Subject"] = "Confirme seu cadastro no MORBiDus"
    msg["From"] = settings.smtp_from
    msg["To"] = para
    msg.set_content(
        f"Olá, {nome}.\n\n"
        f"Para ativar sua conta no MORBiDus, abra o link abaixo nas próximas 24 horas:\n\n{link}\n\n"
        "Se você não pediu este cadastro, ignore este e-mail.\n\n"
        "MORBiDus · Death Identity Fraud Prevention"
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except Exception:
        log.exception("falha ao enviar e-mail de confirmação")
