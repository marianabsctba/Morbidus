from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from morbidus_common.bus import InMemoryBus
from morbidus_common.events import ObituaryRaw, Topics
from morbidus_common.search import InMemoryDeathIndex
from resolver_svc.config import ResolverSettings
from resolver_svc.main import build_app
from resolver_svc.parsing import parse_data, parse_idade

REF = date(2026, 10, 24)


def test_parse_datas_e_idades():
    assert parse_data("20/10/2026", REF) == date(2026, 10, 20)
    assert parse_data("20/10/26", REF) == date(2026, 10, 20)
    assert parse_data("21 de outubro de 2026", REF) == date(2026, 10, 21)
    assert parse_data("Faleceu em 3 de Março", REF) == date(2026, 3, 3)
    # Sem ano e no futuro em relação à coleta: é do ano anterior.
    assert parse_data("30/12", REF) == date(2025, 12, 30)
    assert parse_data("31/02/2026", REF) is None
    assert parse_idade("82 anos") == 82
    assert parse_idade("1 ano") == 1
    assert parse_idade("idade não informada") is None


@pytest.fixture
def ambiente():
    bus, index = InMemoryBus(), InMemoryDeathIndex()
    app = build_app(ResolverSettings(database_url="sqlite:///:memory:"), bus=bus, index=index)
    with TestClient(app) as client:
        yield client, bus, index


def _raw(event_id, nome, url, data="20/10/2026", idade="82 anos", cidade="Curitiba"):
    return ObituaryRaw(
        event_id=event_id,
        occurred_at=datetime(2026, 10, 24, tzinfo=timezone.utc),
        source_id="teste",
        source_url=url,
        cidade=cidade,
        uf="PR",
        nome=nome,
        idade=idade,
        data_falecimento=data,
    )


async def test_mesma_pessoa_em_duas_fontes_vira_um_registro(ambiente):
    client, bus, index = ambiente
    await bus.publish(Topics.OBITUARY_RAW, _raw("a", "Fulano de Tal da Silva", "https://jornal-a/x"))
    await bus.publish(Topics.OBITUARY_RAW, _raw("b", "Fulano de Tal da Sylva", "https://jornal-b/y", data="21/10/2026"))

    assert len(index.docs) == 1
    doc = next(iter(index.docs.values()))
    assert doc["fontes"] == ["https://jornal-a/x", "https://jornal-b/y"]
    assert doc["ano_nascimento_estimado"] == 1944
    assert client.get(f"/v1/records/{doc['record_id']}").json()["nome"] == "Fulano de Tal da Silva"


async def test_homonimo_em_outra_cidade_nao_e_mesclado(ambiente):
    client, bus, index = ambiente
    await bus.publish(Topics.OBITUARY_RAW, _raw("a", "Fulano de Tal da Silva", "https://a/x"))
    await bus.publish(Topics.OBITUARY_RAW, _raw("b", "Fulano de Tal da Silva", "https://b/y", cidade="Londrina"))
    assert len(index.docs) == 2
    stats = client.get("/v1/estatisticas").json()
    assert stats["total"] == 2
    assert stats["por_uf"] == [{"uf": "PR", "total": 2, "cidades": {"Curitiba": 1, "Londrina": 1}}]
    assert "Fulano" not in str(stats)


async def test_data_de_nascimento_separa_homonimos(ambiente):
    _, bus, index = ambiente
    a = _raw("a", "Fulano de Tal da Silva", "https://a/x", idade=None)
    b = _raw("b", "Fulano de Tal da Silva", "https://b/y", idade=None)
    c = _raw("c", "Fulano de Tal da Silva", "https://c/z", idade=None)
    a.data_nascimento, b.data_nascimento, c.data_nascimento = "01/02/1950", "01/02/1950", "15/08/1961"
    for evento in (a, b, c):
        await bus.publish(Topics.OBITUARY_RAW, evento)
    assert len(index.docs) == 2
    mesclado = next(d for d in index.docs.values() if d["data_nascimento"] == "1950-02-01")
    assert len(mesclado["fontes"]) == 2
    assert mesclado["idade"] == 76
    assert mesclado["ano_nascimento_estimado"] == 1950


async def test_evento_repetido_e_ignorado(ambiente):
    _, bus, _ = ambiente
    evento = _raw("a", "Fulano de Tal da Silva", "https://a/x")
    await bus.publish(Topics.OBITUARY_RAW, evento)
    await bus.publish(Topics.OBITUARY_RAW, evento)
    normalizados = [t for t, _ in bus.published if t == Topics.DEATH_RECORD_NORMALIZED]
    assert len(normalizados) == 1



def test_canarios_ficam_fora_das_estatisticas_e_so_admin_ve(ambiente):
    client, _, index = ambiente
    admin = {"X-Tenant-Id": "adm", "X-Papel": "admin"}
    assert client.post("/v1/canarios", json={"quantidade": 3}, headers={"X-Tenant-Id": "t1"}).status_code == 403
    plantados = client.post("/v1/canarios", json={"quantidade": 3}, headers=admin).json()
    assert len(plantados) == 3 and len({c["nome"] for c in plantados}) == 3
    assert all(doc["canario"] for doc in index.docs.values())
    assert client.get("/v1/estatisticas").json()["total"] == 0
    assert [c["nome"] for c in client.get("/v1/canarios", headers=admin).json()]
    assert client.get("/v1/canarios", headers={"X-Tenant-Id": "t1"}).status_code == 403


async def test_canario_nao_usa_nome_parecido_com_pessoa_real(ambiente):
    from resolver_svc import canarios

    client, bus, index = ambiente
    await bus.publish(Topics.OBITUARY_RAW, _raw("a", "Gumercindo Belarmino Quintanilha", "https://a/x"))
    # Sorteio viciado: a primeira combinação colide com a pessoa real e deve ser descartada.
    import random as _r

    class Viciado(_r.Random):
        def __init__(self):
            super().__init__(7)
            self.vez = 0

        def choice(self, seq):
            self.vez += 1
            if self.vez <= 3:
                return {"Gumercindo", "Belarmino", "Quintanilha"}.intersection(seq).pop()
            return super().choice(seq)

    original = canarios.random.SystemRandom
    canarios.random.SystemRandom = Viciado
    try:
        plantados = client.post("/v1/canarios", json={"quantidade": 1}, headers={"X-Tenant-Id": "adm", "X-Papel": "admin"}).json()
    finally:
        canarios.random.SystemRandom = original
    assert plantados[0]["nome"] != "GUMERCINDO BELARMINO QUINTANILHA"



async def test_reindexar_reconstroi_o_indice(ambiente):
    client, bus, index = ambiente
    await bus.publish(Topics.OBITUARY_RAW, _raw("a", "Fulano de Tal da Silva", "https://a/x"))
    index.docs.clear()
    assert client.post("/interno/reindexar").json() == {"reindexados": 1}
    assert len(index.docs) == 1
