from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    """Configuração comum a todos os serviços; cada um estende com o que precisa."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    log_level: str = "INFO"
    bus_backend: str = "memory"  # memory | kafka
    kafka_bootstrap: str = "localhost:9092"
