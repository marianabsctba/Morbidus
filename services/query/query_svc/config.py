from morbidus_common.settings import ServiceSettings


class QuerySettings(ServiceSettings):
    provider_url: str = "http://localhost:8002"
    provider_timeout_seconds: float = 8.0
    # Contagem de identidade quente (audit-svc, rota interna).
    audit_url: str = "http://audit:8000"
    calor_outras_instituicoes: int = 2
    calor_janela_dias: int = 7
    search_backend: str = "memory"  # memory | opensearch
    opensearch_url: str = "http://localhost:9200"
    # Segredo do HMAC do CPF no log de auditoria: permite achar todas as
    # consultas de um CPF sem guardar o número em claro.
    audit_cpf_salt: str = "troque-em-producao"
    sinal_forte_min: float = 0.85
    sinal_fraco_min: float = 0.6
