from morbidus_common.settings import ServiceSettings


class AuditSettings(ServiceSettings):
    database_url: str = "sqlite:///./audit.db"
