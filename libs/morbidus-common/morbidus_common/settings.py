from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    """Configuração comum a todos os serviços; cada um estende com o que precisa."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    log_level: str = "INFO"
    bus_backend: str = "memory"  # memory | kafka
    kafka_bootstrap: str = "localhost:9092"


class SmtpSettings(ServiceSettings):
    """Envio de e-mail. Sem SMTP_HOST, nada é enviado."""

    public_url: str = "http://localhost:8080"
    smtp_host: str = ""
    smtp_port: int = 587
    # SSL direto (porta 465). Com False, usa STARTTLS.
    smtp_ssl: bool = False
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "MORBiDus <nao-responda@localhost>"
