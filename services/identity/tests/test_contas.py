import pytest
from fastapi.testclient import TestClient
from identity_svc import contas
from identity_svc.config import IdentitySettings
from identity_svc.main import build_app

CADASTRO = {
    "nome": "Analista Exemplo",
    "email": "Analista@Exemplo.com",
    "senha": "senha-bem-longa-123",
    "organizacao": "Cooperativa Exemplo",
    "uso_pretendido": "prevencao_fraude",
    "aceite_termos": True,
}
CONSULTA = {"X-Forwarded-Method": "POST", "X-Forwarded-Uri": "/v1/consultas"}


def _client(**extra) -> TestClient:
    extra.setdefault("api_keys_habilitadas", True)
    settings = IdentitySettings(
        database_url="sqlite:///:memory:", admin_token="adm", cookie_secure=False, limite_diario_padrao=2, **extra
    )
    return TestClient(build_app(settings))


@pytest.fixture
def client():
    with _client() as c:
        yield c


def _cadastrar_e_liberar(client, cadastro=CADASTRO):
    assert client.post("/v1/contas", json=cadastro).status_code == 201
    email = cadastro["email"].lower()
    assert client.patch(f"/v1/admin/usuarios/{email}", json={"email_verificado": True}, headers={"X-Admin-Token": "adm"}).status_code == 200


def _ativar_mfa(client) -> list[str]:
    from identity_svc import mfa

    inicio = client.post("/v1/conta/mfa/iniciar").json()
    assert inicio["uri"].startswith("otpauth://totp/")
    codigo = mfa._hotp(inicio["segredo"], mfa.passo_atual())
    resp = client.post("/v1/conta/mfa/ativar", json={"codigo": codigo})
    assert resp.status_code == 200, resp.text
    return resp.json()["codigos_recuperacao"]


def _entrar(client, senha=CADASTRO["senha"]):
    return client.post("/v1/sessao", json={"email": "analista@exemplo.com", "senha": senha})


def test_cadastro_login_e_conta(client):
    resp = client.post("/v1/contas", json=CADASTRO)
    assert resp.status_code == 201
    assert resp.json() == {"verificacao_necessaria": False, "aprovacao_necessaria": True}
    assert client.post("/v1/contas", json=CADASTRO).status_code == 409

    # Sem SMTP, a conta só entra depois de aprovada.
    pendente = _entrar(client)
    assert pendente.status_code == 403 and "aprovação" in pendente.json()["detail"]
    client.patch("/v1/admin/usuarios/analista@exemplo.com", json={"email_verificado": True}, headers={"X-Admin-Token": "adm"})

    login = _entrar(client)
    assert login.status_code == 200
    cookie = login.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie

    conta = client.get("/v1/conta").json()
    assert conta["email"] == "analista@exemplo.com"
    assert conta["limite_diario"] == 2 and conta["consultas_hoje"] == 0

    client.delete("/v1/sessao")
    assert client.get("/v1/conta").status_code == 401


def test_validacoes_do_cadastro(client):
    for campo, valor in [("senha", "curta"), ("email", "sem-arroba"), ("aceite_termos", False)]:
        assert client.post("/v1/contas", json={**CADASTRO, campo: valor}).status_code == 422


def test_sessao_passa_no_forwardauth_e_cota_diaria(client):
    _cadastrar_e_liberar(client)
    assert client.get("/auth/verify").status_code == 401
    _entrar(client)

    leitura = client.get("/auth/verify", headers={"X-Forwarded-Method": "GET", "X-Forwarded-Uri": "/v1/auditoria"})
    assert leitura.status_code == 200 and leitura.headers["X-Api-Key-Id"] == ""
    assert client.get("/auth/verify", headers=CONSULTA).status_code == 200
    assert client.get("/auth/verify", headers=CONSULTA).status_code == 200
    estourou = client.get("/auth/verify", headers=CONSULTA)
    assert estourou.status_code == 429
    # Leituras continuam liberadas mesmo com a cota esgotada.
    assert client.get("/auth/verify", headers={"X-Forwarded-Method": "GET", "X-Forwarded-Uri": "/v1/auditoria"}).status_code == 200
    assert client.get("/v1/conta").json()["consultas_hoje"] == 2


def test_api_key_self_service_soma_na_mesma_cota(client):
    _cadastrar_e_liberar(client)
    _entrar(client)
    nova = client.post("/v1/conta/api-keys", json={"nome": "integração"}).json()
    assert nova["chave"].startswith("mbd_")
    assert [k["prefixo"] for k in client.get("/v1/conta/api-keys").json()] == [nova["prefixo"]]
    assert "chave" not in client.get("/v1/conta/api-keys").json()[0]

    sessao = client.cookies.get(contas.COOKIE)
    client.cookies.clear()
    via_api = {**CONSULTA, "X-API-Key": nova["chave"]}
    assert client.get("/auth/verify", headers=via_api).headers["X-Api-Key-Id"] == nova["id"]
    assert client.get("/auth/verify", headers=via_api).status_code == 200
    assert client.get("/auth/verify", headers=via_api).status_code == 429

    client.cookies.set(contas.COOKIE, sessao)
    assert client.delete(f"/v1/conta/api-keys/{nova['id']}").status_code == 204
    client.cookies.clear()
    assert client.get("/auth/verify", headers={"X-API-Key": nova["chave"]}).status_code == 401


def test_bloqueio_apos_senhas_erradas(client):
    _cadastrar_e_liberar(client)
    for _ in range(5):
        assert _entrar(client, senha="errada-errada").status_code == 401
    assert _entrar(client).status_code == 429


def test_admin_libera_limite(client):
    _cadastrar_e_liberar(client)
    adm = {"X-Admin-Token": "adm"}
    assert client.patch("/v1/admin/usuarios/analista@exemplo.com", json={"limite_diario": 0}, headers=adm).status_code == 200
    _entrar(client)
    for _ in range(5):
        assert client.get("/auth/verify", headers=CONSULTA).status_code == 200


def test_porta_465_usa_ssl_direto(monkeypatch):
    from identity_svc import correio

    usados = []

    class Falso:
        def __init__(self, host, port, timeout):
            usados.append((type(self).__name__, port))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            usados.append("starttls")

        def login(self, u, s):
            usados.append("login")

        def send_message(self, m):
            usados.append(m["To"])

    monkeypatch.setattr(correio.smtplib, "SMTP_SSL", type("SMTP_SSL", (Falso,), {}))
    monkeypatch.setattr(correio.smtplib, "SMTP", type("SMTP", (Falso,), {}))
    base = dict(smtp_host="smtp.exemplo", smtp_user="u@exemplo.com", smtp_from="MORBiDus <u@exemplo.com>")
    correio.envia_confirmacao(IdentitySettings(smtp_port=465, **base), "a@b.com", "A", "tok")
    correio.envia_confirmacao(IdentitySettings(smtp_port=587, **base), "c@d.com", "C", "tok")
    assert usados == [("SMTP_SSL", 465), "login", "a@b.com", ("SMTP", 587), "starttls", "login", "c@d.com"]


def test_confirmacao_de_email(monkeypatch):
    enviados = []
    monkeypatch.setattr(contas, "envia_confirmacao", lambda s, para, nome, token: enviados.append(token))
    with _client(smtp_host="smtp.exemplo") as client:
        assert client.post("/v1/contas", json=CADASTRO).json() == {"verificacao_necessaria": True, "aprovacao_necessaria": False}
        assert _entrar(client).status_code == 403
        assert client.post("/v1/contas/verificar", json={"token": "falso"}).status_code == 400
        assert client.post("/v1/contas/verificar", json={"token": enviados[0]}).status_code == 200
        assert _entrar(client).status_code == 200


def test_admin_aprova_bloqueia_e_ve_todos(client):
    outra = {**CADASTRO, "email": "outra@exemplo.com", "nome": "Outra Pessoa"}
    _cadastrar_e_liberar(client)
    client.post("/v1/contas", json=outra)
    _entrar(client)
    # Sem papel de admin, a área é negada.
    assert client.get("/v1/conta/admin/usuarios").status_code == 403
    assert client.get("/auth/verify").headers["X-Papel"] == ""

    client.patch("/v1/admin/usuarios/analista@exemplo.com", json={"admin": True}, headers={"X-Admin-Token": "adm"})
    assert client.get("/v1/conta").json()["admin"] is True
    # Admin sem MFA ainda não tem poderes.
    assert client.get("/auth/verify").headers["X-Papel"] == ""
    assert "MFA" in client.get("/v1/conta/admin/usuarios").json()["detail"]
    recuperacao = _ativar_mfa(client)
    assert client.get("/auth/verify").headers["X-Papel"] == "admin"

    usuarios = {u["email"]: u for u in client.get("/v1/conta/admin/usuarios").json()}
    assert usuarios["outra@exemplo.com"]["liberado"] is False
    eu = usuarios["analista@exemplo.com"]
    assert client.patch(f"/v1/conta/admin/usuarios/{eu['id']}", json={"admin": False}).status_code == 400

    alvo = usuarios["outra@exemplo.com"]["id"]
    aprovada = client.patch(f"/v1/conta/admin/usuarios/{alvo}", json={"liberado": True, "limite_diario": 0}).json()
    assert aprovada["liberado"] is True and aprovada["limite_diario"] == 0

    client.cookies.clear()
    assert client.post("/v1/sessao", json={"email": "outra@exemplo.com", "senha": CADASTRO["senha"]}).status_code == 200
    client.cookies.clear()
    desafio = _entrar(client).json()["desafio"]
    assert client.post("/v1/sessao/mfa", json={"desafio": desafio, "codigo": recuperacao[0]}).status_code == 200
    client.patch(f"/v1/conta/admin/usuarios/{alvo}", json={"ativo": False})
    client.cookies.clear()
    assert client.post("/v1/sessao", json={"email": "outra@exemplo.com", "senha": CADASTRO["senha"]}).status_code == 403


def test_api_key_de_conta_pendente_nao_passa(client):
    _cadastrar_e_liberar(client)
    _entrar(client)
    chave = client.post("/v1/conta/api-keys", json={"nome": "x1"}).json()["chave"]
    client.patch("/v1/admin/usuarios/analista@exemplo.com", json={"email_verificado": False}, headers={"X-Admin-Token": "adm"})
    client.cookies.clear()
    assert client.get("/auth/verify", headers={"X-API-Key": chave}).status_code == 403


def test_api_desligada_por_padrao():
    with _client(api_keys_habilitadas=False) as client:
        _cadastrar_e_liberar(client)
        _entrar(client)
        assert client.post("/v1/conta/api-keys", json={"nome": "x1"}).status_code in (404, 405)
        assert client.get("/v1/conta/api-keys").status_code == 404
        client.cookies.clear()
        assert client.get("/auth/verify", headers={"X-API-Key": "mbd_qualquer_coisa"}).status_code == 401


def test_login_com_mfa(client):
    from identity_svc import mfa

    _cadastrar_e_liberar(client)
    _entrar(client)
    assert client.get("/v1/conta").json()["mfa_ativo"] is False
    assert client.post("/v1/conta/mfa/ativar", json={"codigo": "000000"}).status_code == 409
    inicio = client.post("/v1/conta/mfa/iniciar").json()
    assert client.post("/v1/conta/mfa/ativar", json={"codigo": "000000"}).status_code == 400
    codigo = mfa._hotp(inicio["segredo"], mfa.passo_atual())
    recuperacao = client.post("/v1/conta/mfa/ativar", json={"codigo": codigo}).json()["codigos_recuperacao"]
    assert len(recuperacao) == 8

    client.delete("/v1/sessao")
    client.cookies.clear()
    primeira = _entrar(client)
    assert primeira.json()["mfa"] is True and "set-cookie" not in primeira.headers
    desafio = primeira.json()["desafio"]
    assert client.post("/v1/sessao/mfa", json={"desafio": desafio, "codigo": "123456"}).status_code == 401
    # O mesmo código do app não vale duas vezes.
    assert client.post("/v1/sessao/mfa", json={"desafio": desafio, "codigo": codigo}).status_code == 401
    ok = client.post("/v1/sessao/mfa", json={"desafio": desafio, "codigo": recuperacao[0].upper()})
    assert ok.status_code == 200 and "set-cookie" in ok.headers
    assert client.get("/v1/conta").status_code == 200

    # Código de recuperação só funciona uma vez; desafio usado não volta.
    client.cookies.clear()
    desafio2 = _entrar(client).json()["desafio"]
    assert client.post("/v1/sessao/mfa", json={"desafio": desafio2, "codigo": recuperacao[0]}).status_code == 401
    assert client.post("/v1/sessao/mfa", json={"desafio": desafio, "codigo": recuperacao[1]}).status_code == 401


def test_desafio_mfa_trava_apos_5_erros(client):
    _cadastrar_e_liberar(client)
    _entrar(client)
    _ativar_mfa(client)
    client.cookies.clear()
    desafio = _entrar(client).json()["desafio"]
    for _ in range(5):
        assert client.post("/v1/sessao/mfa", json={"desafio": desafio, "codigo": "000000"}).status_code == 401
    assert client.post("/v1/sessao/mfa", json={"desafio": desafio, "codigo": "000000"}).status_code == 429


def test_admin_nao_desativa_mfa_e_reset_pelo_token(client):
    _cadastrar_e_liberar(client)
    _entrar(client)
    recuperacao = _ativar_mfa(client)
    client.patch("/v1/admin/usuarios/analista@exemplo.com", json={"admin": True}, headers={"X-Admin-Token": "adm"})
    assert client.post("/v1/conta/mfa/desativar", json={"codigo": recuperacao[0]}).status_code == 400
    client.patch("/v1/admin/usuarios/analista@exemplo.com", json={"resetar_mfa": True}, headers={"X-Admin-Token": "adm"})
    assert client.get("/v1/conta").json()["mfa_ativo"] is False
    client.cookies.clear()
    assert _entrar(client).json()["mfa"] is False
