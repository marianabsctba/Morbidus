from fastapi.testclient import TestClient
from morbidus_common.text import cpf_with_check_digits
from provider_svc.config import ProviderSettings
from provider_svc.main import build_app
from provider_svc.providers import DeathProvider


class ProvedorQuebrado(DeathProvider):
    name = "quebrado"

    def __init__(self):
        self.chamadas = 0

    async def lookup(self, cpf):
        self.chamadas += 1
        raise RuntimeError("fora do ar")


def test_mock_identifica_falecido_e_regular():
    client = TestClient(build_app(ProviderSettings(mock_deceased_bases="111444777")))
    falecido = client.post("/v1/lookup", json={"cpf": cpf_with_check_digits("111444777")}).json()
    assert falecido["resultados"][0]["status"] == "falecido"
    regular = client.post("/v1/lookup", json={"cpf": cpf_with_check_digits("123456789")}).json()
    assert regular["resultados"][0]["status"] == "regular"


def test_cpf_invalido_retorna_422():
    client = TestClient(build_app(ProviderSettings()))
    assert client.post("/v1/lookup", json={"cpf": "111.111.111-11"}).status_code == 422
    assert client.post("/v1/lookup", json={"cpf": "123"}).status_code == 422


def test_circuit_breaker_para_de_chamar_provedor_quebrado():
    quebrado = ProvedorQuebrado()
    client = TestClient(build_app(ProviderSettings(breaker_failures=2), providers=[quebrado]))
    cpf = cpf_with_check_digits("123456789")
    for _ in range(4):
        resp = client.post("/v1/lookup", json={"cpf": cpf}).json()
        assert resp["resultados"][0]["status"] == "indisponivel"
    assert quebrado.chamadas == 2
