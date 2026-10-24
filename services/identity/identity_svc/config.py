from morbidus_common.settings import ServiceSettings


class IdentitySettings(ServiceSettings):
    database_url: str = "sqlite:///./identity.db"
    # Sem ADMIN_TOKEN definido, as rotas de administração recusam tudo.
    admin_token: str = ""
    # Segredo misturado ao hash das API keys; vazamento do banco sozinho não basta.
    api_key_pepper: str = "troque-em-producao"

    # Consultas por dia para cada conta (painel e API keys somados).
    limite_diario_padrao: int = 50
    max_api_keys_por_conta: int = 5
    sessao_horas: int = 12
    # Desligue só em desenvolvimento sem HTTPS fora de localhost.
    cookie_secure: bool = True

    # Confirmação de e-mail. Sem SMTP_HOST, a conta já nasce ativa.
    public_url: str = "http://localhost:8080"
    smtp_host: str = ""
    smtp_port: int = 587
    # SSL direto (porta 465). Com False, usa STARTTLS.
    smtp_ssl: bool = False
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "MORBiDus <nao-responda@localhost>"
