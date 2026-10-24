from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient
from morbidus_common.bus import InMemoryBus
from morbidus_common.events import DeathRecordNormalized, Topics
from morbidus_common.search import InMemoryDeathIndex
from morbidus_common.text import cpf_with_check_digits, normalize_name, phonetic_key
from query_svc.config import QuerySettings
from query_svc.main import build_app

TENANT = {"X-Tenant-Id": "t1", "X-Api-Key-Id": "k1"}
CPF_FALECIDO = cpf_with_check_digits("111444777")
CPF_REGULAR = cpf_with_check_digits("123456789")


def _provider(request: httpx.Request) -> httpx.Response:
    cpf = request.read().decode()
    status = "falecido" if CPF_FALECIDO in cpf else "regular"
    return httpx.Response(200, json={"resultados": [{"provider": "mock", "status": status, "ano_obito": 2023}]})


def _registro(nome="Fulano de Tal da Silva", cidade="Curitiba", ano_nascimento=1944):
    return DeathRecordNormalized(
        record_id="r1",
        nome=nome,
        nome_normalizado=normalize_name(nome),
        chave_fonetica=phonetic_key(nome),
        idade=82,
        data_falecimento=date(2026, 10, 20),
        ano_nascimento_estimado=ano_nascimento,
        cidade=cidade,
        uf="PR",
        fontes=["https://jornal/x"],
    )


@pytest.fixture
def ambiente():
    bus, index = InMemoryBus(), InMemoryDeathIndex()
    index.upsert(_registro())
    provider = httpx.AsyncClient(transport=httpx.MockTransport(_provider), base_url="http://provider")
    with TestClient(build_app(QuerySettings(), bus=bus, index=index, provider_client=provider)) as client:
        yield client, bus


def test_sem_tenant_e_recusado(ambiente):
    client, _ = ambiente
    resp = client.post("/v1/consultas", json={"cpf": CPF_FALECIDO, "finalidade": "onboarding"})
    assert resp.status_code == 401


def test_validacoes_de_entrada(ambiente):
    client, _ = ambiente
    assert client.post("/v1/consultas", json={"finalidade": "onboarding"}, headers=TENANT).status_code == 422
    assert client.post("/v1/consultas", json={"nome": "Fulano", "finalidade": "onboarding"}, headers=TENANT).status_code == 422
    assert client.post("/v1/consultas", json={"cpf": "12345678900", "finalidade": "onboarding"}, headers=TENANT).status_code == 422
    assert client.post("/v1/consultas", json={"cpf": CPF_REGULAR}, headers=TENANT).status_code == 422


def test_cpf_falecido_confirma_e_audita_sem_cpf_em_claro(ambiente):
    client, bus = ambiente
    resp = client.post("/v1/consultas", json={"cpf": CPF_FALECIDO, "finalidade": "concessao_credito"}, headers=TENANT)
    body = resp.json()
    assert body["status"] == "obito_confirmado"
    assert body["score"] == 1.0
    topic, evento = bus.published[-1]
    assert topic == Topics.QUERY_PERFORMED
    assert evento["tenant_id"] == "t1"
    assert evento["finalidade"] == "concessao_credito"
    assert CPF_FALECIDO not in str(evento)
    assert evento["cpf_mascarado"] == "***.444.777-**"


def test_nome_com_dados_compativeis_gera_sinal_forte(ambiente):
    client, _ = ambiente
    resp = client.post(
        "/v1/consultas",
        json={
            "nome": "Fulano Tal da Sylva",
            "uf": "PR",
            "cidade": "Curitiba",
            "data_nascimento": "1944-05-10",
            "finalidade": "prevencao_fraude",
        },
        headers=TENANT,
    ).json()
    assert resp["status"] == "sinal_forte"
    assert resp["aviso"]
    assert resp["evidencias"][0]["tipo"] == "obituario"


def test_idade_incompativel_derruba_o_score(ambiente):
    client, _ = ambiente
    resp = client.post(
        "/v1/consultas",
        json={"nome": "Fulano de Tal da Silva", "uf": "PR", "data_nascimento": "1990-01-01", "finalidade": "onboarding"},
        headers=TENANT,
    ).json()
    assert resp["status"] in ("sinal_fraco", "sem_registro")


def test_data_de_nascimento_exata_pesa_mais_que_o_ano():
    from query_svc.scoring import score_candidate

    candidato = {**_registro().model_dump(mode="json"), "data_nascimento": "1944-05-10"}
    exato, motivos = score_candidate(candidato, "Fulano de Tal da Silva", "PR", None, date(1944, 5, 10))
    diferente, _ = score_candidate(candidato, "Fulano de Tal da Silva", "PR", None, date(1944, 7, 1))
    assert "data de nascimento idêntica" in motivos
    assert exato >= 0.95 > 0.6 > diferente


def test_provider_fora_do_ar_nao_derruba_consulta():
    def quebrado(request):
        return httpx.Response(503)

    provider = httpx.AsyncClient(transport=httpx.MockTransport(quebrado), base_url="http://provider")
    with TestClient(build_app(QuerySettings(), bus=InMemoryBus(), index=InMemoryDeathIndex(), provider_client=provider)) as client:
        resp = client.post("/v1/consultas", json={"cpf": CPF_FALECIDO, "finalidade": "onboarding"}, headers=TENANT).json()
    assert resp["status"] == "sem_registro"
    assert resp["fontes_indisponiveis"] == ["provider-svc"]


def test_fontes_da_evidencia_so_para_admin(ambiente):
    client, _ = ambiente
    corpo = {"nome": "Fulano de Tal da Silva", "uf": "PR", "finalidade": "prevencao_fraude"}
    comum = client.post("/v1/consultas", json=corpo, headers=TENANT).json()
    assert "fontes" not in comum["evidencias"][0]["detalhes"]
    admin = client.post("/v1/consultas", json=corpo, headers={**TENANT, "X-Papel": "admin"}).json()
    assert admin["evidencias"][0]["detalhes"]["fontes"] == ["https://jornal/x"]


def test_registra_ip_e_user_agent_de_quem_consultou(ambiente):
    client, bus = ambiente
    headers = {**TENANT, "X-Real-Ip": "203.0.113.9", "User-Agent": "Navegador Teste/1.0"}
    client.post("/v1/consultas", json={"cpf": CPF_REGULAR, "finalidade": "onboarding"}, headers=headers)
    evento = bus.published[-1][1]
    assert evento["ip_origem"] == "203.0.113.9"
    assert evento["user_agent"] == "Navegador Teste/1.0"
    # IP inválido no cabeçalho não é gravado como se fosse IP.
    client.post("/v1/consultas", json={"cpf": CPF_REGULAR, "finalidade": "onboarding"}, headers={**TENANT, "X-Real-Ip": "<script>"})
    assert bus.published[-1][1]["ip_origem"] == "testclient"
