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
