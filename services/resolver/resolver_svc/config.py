from morbidus_common.settings import ServiceSettings


class ResolverSettings(ServiceSettings):
    database_url: str = "sqlite:///./resolver.db"
    search_backend: str = "memory"  # memory | opensearch
    opensearch_url: str = "http://localhost:9200"
    # Duas entradas da mesma pessoa podem trazer datas um pouco diferentes
    # (falecimento num jornal, sepultamento em outro).
    dedup_window_days: int = 3
