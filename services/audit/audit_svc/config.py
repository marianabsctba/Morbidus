from morbidus_common.settings import SmtpSettings


class AuditSettings(SmtpSettings):
    database_url: str = "sqlite:///./audit.db"
    # De onde vem a lista de administradoras que recebem os alertas por e-mail.
    identity_url: str = "http://identity:8000"

    # Detector de abuso (ver audit_svc/sentinela.py).
    rajada_limite: int = 20
    varredura_limite: int = 15
    obito_recente_dias: int = 30
    obitos_recentes_limite: int = 5
    taxa_minimo_consultas: int = 10
    taxa_acerto_limite: float = 0.6
    ip_contas_limite: int = 3
    alerta_silencio_horas: int = 6
    # Identidade quente: instituições diferentes batendo na mesma pessoa falecida.
    calor_instituicoes: int = 3
    calor_janela_dias: int = 7
    # Tokens de leitura do feed TAXII, separados por vírgula. Vazio desliga o TAXII.
    cti_taxii_tokens: str = ""
