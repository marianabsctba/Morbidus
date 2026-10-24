from morbidus_common.settings import ServiceSettings


class ProviderSettings(ServiceSettings):
    # Provedores ativos, separados por vírgula. Serpro e CRC entram aqui
    # quando houver contrato e credenciais.
    enabled_providers: str = "mock"
    # Os 9 primeiros dígitos dos CPFs que o mock trata como falecidos.
    mock_deceased_bases: str = "111444777,529982247"
    provider_timeout_seconds: float = 5.0
    cache_ttl_seconds: int = 3600
    breaker_failures: int = 5
    breaker_reset_seconds: int = 30
