from morbidus_common.settings import ServiceSettings


class CrawlerSettings(ServiceSettings):
    # Spiders ativos, separados por vírgula. "fixture" usa dados fictícios locais.
    enabled_spiders: str = "fixture"
    # 0 desliga o agendador; as coletas passam a ser só sob demanda.
    crawl_interval_minutes: int = 0
    user_agent: str = "MORBiDusBot/0.1 (+https://github.com/marianabsctba/Morbidus)"
    request_delay_seconds: float = 5.0
    raw_store_backend: str = "memory"  # memory | minio
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "morbidus"
    minio_secret_key: str = "morbidus-dev"
    minio_bucket: str = "obituarios-raw"
    minio_secure: bool = False
