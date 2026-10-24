from morbidus_common.settings import SmtpSettings


class IdentitySettings(SmtpSettings):
    database_url: str = "sqlite:///./identity.db"
    # Sem ADMIN_TOKEN definido, as rotas de administração recusam tudo.
    admin_token: str = ""
    # Segredo misturado ao hash das API keys; vazamento do banco sozinho não basta.
    api_key_pepper: str = "troque-em-producao"

    # Consultas por dia para cada conta (painel e API keys somados).
    limite_diario_padrao: int = 50
    # Acesso por API key desligado: só o painel (sessão) consulta. Ligue só para parceiros específicos.
    api_keys_habilitadas: bool = False
    max_api_keys_por_conta: int = 5
    sessao_horas: int = 12
    # Desligue só em desenvolvimento sem HTTPS fora de localhost.
    cookie_secure: bool = True
    # Confirmação de e-mail: campos SMTP_* herdados de SmtpSettings.
