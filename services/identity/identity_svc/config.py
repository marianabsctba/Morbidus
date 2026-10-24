from morbidus_common.settings import ServiceSettings


class IdentitySettings(ServiceSettings):
    database_url: str = "sqlite:///./identity.db"
    # Sem ADMIN_TOKEN definido, as rotas de administração recusam tudo.
    admin_token: str = ""
    # Segredo misturado ao hash das API keys; vazamento do banco sozinho não basta.
    api_key_pepper: str = "troque-em-producao"
