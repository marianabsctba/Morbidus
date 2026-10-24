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
    settings = IdentitySettings(
        database_url="sqlite:///:memory:", admin_token="adm", cookie_secure=False, limite_diario_padrao=2, **extra
    )
    return TestClient(build_app(settings))


@pytest.fixture
def client():
    with _client() as c:
        yield c


def _entrar(client, senha=CADASTRO["senha"]):
    return client.post("/v1/sessao", json={"email": "analista@exemplo.com", "senha": senha})


def test_cadastro_login_e_conta(client):
    resp = client.post("/v1/contas", json=CADASTRO)
    assert resp.status_code == 201 and resp.json() == {"verificacao_necessaria": False}
    assert client.post("/v1/contas", json=CADASTRO).status_code == 409

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
    client.post("/v1/contas", json=CADASTRO)
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
    client.post("/v1/contas", json=CADASTRO)
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
    client.post("/v1/contas", json=CADASTRO)
    for _ in range(5):
        assert _entrar(client, senha="errada-errada").status_code == 401
    assert _entrar(client).status_code == 429


def test_admin_libera_limite(client):
    client.post("/v1/contas", json=CADASTRO)
    adm = {"X-Admin-Token": "adm"}
    assert client.patch("/v1/admin/usuarios/analista@exemplo.com", json={"limite_diario": 0}, headers=adm).status_code == 200
    _entrar(client)
    for _ in range(5):
        assert client.get("/auth/verify", headers=CONSULTA).status_code == 200


def test_confirmacao_de_email(monkeypatch):
    enviados = []
    monkeypatch.setattr(contas, "envia_confirmacao", lambda s, para, nome, token: enviados.append(token))
    with _client(smtp_host="smtp.exemplo") as client:
        assert client.post("/v1/contas", json=CADASTRO).json() == {"verificacao_necessaria": True}
        assert _entrar(client).status_code == 403
        assert client.post("/v1/contas/verificar", json={"token": "falso"}).status_code == 400
        assert client.post("/v1/contas/verificar", json={"token": enviados[0]}).status_code == 200
        assert _entrar(client).status_code == 200
