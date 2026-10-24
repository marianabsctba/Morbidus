from datetime import datetime, timedelta, timezone

import pytest
from audit_svc import main as audit_main
from audit_svc.config import AuditSettings
from audit_svc.main import build_app
from fastapi.testclient import TestClient
from morbidus_common.bus import InMemoryBus
from morbidus_common.events import QueryPerformed, QueryStatus, Topics

ADMIN = {"X-Tenant-Id": "adm", "X-Papel": "admin"}
INICIO = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def ambiente(monkeypatch):
    avisos = []
    monkeypatch.setattr(audit_main, "notificar", lambda settings, alertas: avisos.extend(a.regra for a in alertas))
    bus = InMemoryBus()
    with TestClient(build_app(AuditSettings(database_url="sqlite:///:memory:"), bus=bus)) as client:
        yield client, bus, avisos


def _consulta(
    tenant="t1", minuto=0, nome=None, status=QueryStatus.SEM_REGISTRO, dias=None, ip="203.0.113.9", n=0,
    identidades=(), canario=False,
):
    return QueryPerformed(
        event_id=f"{tenant}-{minuto}-{n}-{nome}-{ip}",
        occurred_at=INICIO + timedelta(minutes=minuto),
        query_id=f"q{minuto}{n}",
        tenant_id=tenant,
        finalidade="onboarding",
        nome_consultado=nome,
        status=status,
        score=0.0,
        fontes_consultadas=["obituario"],
        ip_origem=ip,
        dias_desde_obito=dias,
        identidades=list(identidades),
        canario=canario,
    )


async def _publica(bus, eventos):
    for e in eventos:
        await bus.publish(Topics.QUERY_PERFORMED, e)


def _alertas(client, status="aberto"):
    return client.get(f"/v1/alertas?status={status}", headers=ADMIN).json()


async def test_rajada_e_sem_repeticao(ambiente):
    client, bus, avisos = ambiente
    await _publica(bus, [_consulta(minuto=i // 3, n=i) for i in range(25)])
    alertas = _alertas(client)
    assert [a["regra"] for a in alertas] == ["rajada"]
    assert alertas[0]["descricao"] == "20 consultas em 10 minutos"
    assert avisos == ["rajada"]


async def test_uso_normal_nao_gera_alerta(ambiente):
    client, bus, avisos = ambiente
    # 12 consultas espalhadas em 12 horas, quase todas "nada consta": onboarding legítimo.
    eventos = [_consulta(minuto=60 * i, nome=f"Pessoa {i}") for i in range(12)]
    eventos[3] = _consulta(minuto=180, nome="Pessoa 3", status=QueryStatus.SINAL_FORTE, dias=400)
    await _publica(bus, eventos)
    assert _alertas(client) == [] and avisos == []


async def test_varredura_de_nomes(ambiente):
    client, bus, _ = ambiente
    await _publica(bus, [_consulta(minuto=3 * i, nome=f"Nome {i}") for i in range(16)])
    assert "varredura_nomes" in [a["regra"] for a in _alertas(client)]


async def test_caca_a_obitos_recentes_e_taxa_de_acerto(ambiente):
    client, bus, _ = ambiente
    eventos = [
        _consulta(minuto=30 * i, nome=f"Nome {i}", status=QueryStatus.SINAL_FORTE, dias=7) for i in range(6)
    ] + [_consulta(minuto=200 + 30 * i, nome=f"Outro {i}") for i in range(4)]
    await _publica(bus, eventos)
    regras = {a["regra"]: a for a in _alertas(client)}
    assert "obitos_recentes" in regras
    assert regras["taxa_acerto"]["descricao"] == "60% de acertos em 10 consultas nas últimas 24 horas"


async def test_varias_contas_no_mesmo_ip(ambiente):
    client, bus, _ = ambiente
    await _publica(bus, [_consulta(tenant=f"conta{i}", minuto=i) for i in range(3)])
    (alerta,) = _alertas(client)
    assert alerta["regra"] == "ip_multicontas" and alerta["ip"] == "203.0.113.9" and alerta["tenant_id"] is None


async def test_alertas_so_para_admin_e_resolucao(ambiente):
    client, bus, _ = ambiente
    await _publica(bus, [_consulta(tenant=f"conta{i}", minuto=i) for i in range(3)])
    assert client.get("/v1/alertas", headers={"X-Tenant-Id": "t1"}).status_code == 403
    alerta = _alertas(client)[0]
    resolvido = client.patch(f"/v1/alertas/{alerta['id']}", json={"status": "resolvido"}, headers=ADMIN).json()
    assert resolvido["status"] == "resolvido" and resolvido["resolvido_em"]
    assert _alertas(client) == [] and len(_alertas(client, "resolvido")) == 1
    assert client.patch(f"/v1/alertas/{alerta['id']}", json={"status": "apagado"}, headers=ADMIN).status_code == 422


def test_notificacao_por_email(monkeypatch):
    from audit_svc import alertas as modulo
    from audit_svc.models import Alerta

    enviados = []
    monkeypatch.setattr(modulo, "emails_das_admins", lambda s: ["admin@exemplo.com"])
    monkeypatch.setattr(modulo, "enviar", lambda s, msg: enviados.append(msg))
    alerta = Alerta(regra="rajada", severidade="alta", tenant_id="t1", descricao="20 consultas em 10 minutos")
    modulo.notificar(AuditSettings(smtp_host="smtp.exemplo", public_url="https://morbidus.exemplo"), [alerta])
    (msg,) = enviados
    assert msg["To"] == "admin@exemplo.com" and msg["Subject"] == "[MORBiDus] Alerta: Rajada de consultas"
    assert "https://morbidus.exemplo/admin" in msg.get_content()
    # Sem SMTP configurado, não tenta enviar.
    modulo.notificar(AuditSettings(smtp_host=""), [alerta])
    assert len(enviados) == 1



async def test_identidade_quente_entre_instituicoes(ambiente, monkeypatch):
    client, bus, avisos = ambiente
    avisadas = []
    monkeypatch.setattr(audit_main, "avisar_instituicoes", lambda settings, consultas: avisadas.extend(consultas))
    chave = "registro:abc"
    eventos = [
        _consulta(tenant=f"inst{i}", minuto=60 * i, ip=f"203.0.113.{i}", identidades=[chave], status=QueryStatus.SINAL_FORTE)
        for i in range(3)
    ]
    await _publica(bus, eventos[:2])
    # Duas instituições ainda não bastam; a terceira dispara o alerta e todas são avisadas.
    assert client.get("/interno/calor", params={"tenant": "inst9", "chave": chave}).json() == {chave: 2}
    assert _alertas(client) == []
    await _publica(bus, eventos[2:])
    (alerta,) = _alertas(client)
    assert alerta["regra"] == "identidade_quente" and "3 instituições" in alerta["descricao"]
    assert {t for t, _, _ in avisadas} == {"inst0", "inst1", "inst2"}
    # O calor exclui a própria instituição que consulta.
    assert client.get("/interno/calor", params={"tenant": "inst0", "chave": chave}).json() == {chave: 2}


async def test_canario_gera_alerta_maximo_na_hora(ambiente):
    client, bus, avisos = ambiente
    await _publica(bus, [_consulta(tenant="t9", nome="Gumercindo Belarmino Quaresma", canario=True)])
    (alerta,) = _alertas(client)
    assert alerta["regra"] == "canario" and alerta["severidade"] == "alta" and alerta["tenant_id"] == "t9"
    assert avisos == ["canario"]


def test_aviso_para_instituicoes_sem_dado_da_pessoa(monkeypatch):
    from audit_svc import alertas as modulo

    enviados = []
    monkeypatch.setattr(modulo, "emails_por_tenant", lambda s, tenants: {"a": "a@exemplo.com", "b": "b@exemplo.com"})
    monkeypatch.setattr(modulo, "enviar", lambda s, msg: enviados.append(msg))
    quando = datetime(2026, 10, 24, tzinfo=timezone.utc)
    modulo.avisar_instituicoes(
        AuditSettings(smtp_host="smtp.exemplo"), [("a", "q" * 32, quando), ("b", "r" * 32, quando), ("c", "s" * 32, quando)]
    )
    assert sorted(m["To"] for m in enviados) == ["a@exemplo.com", "b@exemplo.com"]
    corpo = enviados[0].get_content()
    assert "3 instituições" in corpo and "laudo " in corpo and "24/10/2026" in corpo



async def test_feed_stix_e_taxii_so_com_alertas_confirmados(monkeypatch):
    import base64

    from audit_svc import cti

    # Os testes usam a faixa de documentação (198.51.100.0/24), que o feed real descarta.
    monkeypatch.setattr(cti, "compartilhavel", lambda e: e.is_global or str(e).startswith("198.51.100."))
    bus = InMemoryBus()
    settings = AuditSettings(database_url="sqlite:///:memory:", cti_taxii_tokens="tok-feed", public_url="https://m.exemplo")
    monkeypatch.setattr(audit_main, "notificar", lambda s, a: None)
    with TestClient(build_app(settings, bus=bus)) as client:
        await _publica(bus, [_consulta(tenant=f"c{i}", minuto=i, ip="198.51.100.7") for i in range(3)])
        (alerta,) = _alertas(client)

        # Aberto ainda não vai para o feed.
        pacote = client.get("/v1/cti/stix", headers=ADMIN).json()
        assert [o["type"] for o in pacote["objects"]] == ["identity", "marking-definition"]
        assert client.get("/v1/cti/stix", headers={"X-Tenant-Id": "t1"}).status_code == 403

        client.patch(f"/v1/alertas/{alerta['id']}", json={"status": "confirmado"}, headers=ADMIN)
        indicadores = [o for o in client.get("/v1/cti/stix", headers=ADMIN).json()["objects"] if o["type"] == "indicator"]
        assert len(indicadores) == 1
        ind = indicadores[0]
        assert ind["pattern"] == "[ipv4-addr:value = '198.51.100.7']" and ind["object_marking_refs"]
        assert "ip_multicontas" in ind["labels"]

        # TAXII: sem token, 401; Bearer e Basic funcionam.
        base = "/taxii2/morbidus/collections/"
        assert client.get(base).status_code == 401
        bearer = {"Authorization": "Bearer tok-feed"}
        basic = {"Authorization": "Basic " + base64.b64encode(b"misp:tok-feed").decode()}
        assert client.get("/taxii2/", headers=bearer).json()["default"] == "https://m.exemplo/taxii2/morbidus/"
        colecoes = client.get(base, headers=basic)
        assert colecoes.headers["content-type"].startswith("application/taxii+json")
        cid = colecoes.json()["collections"][0]["id"]
        envelope = client.get(f"{base}{cid}/objects/", headers=bearer).json()
        assert envelope["more"] is False and any(o["type"] == "indicator" for o in envelope["objects"])
        depois = client.get(f"{base}{cid}/objects/", params={"added_after": "2030-01-01T00:00:00Z"}, headers=bearer).json()
        assert not any(o["type"] == "indicator" for o in depois["objects"])


def test_ip_privado_nunca_vai_para_o_feed(monkeypatch):
    from audit_svc import cti

    real = cti.compartilhavel
    assert not real(__import__("ipaddress").ip_address("10.0.0.5"))
    assert not real(__import__("ipaddress").ip_address("203.0.113.20"))  # documentação também fica de fora
    monkeypatch.setattr(cti, "compartilhavel", lambda e: real(e) or str(e).startswith("203.0.113."))
    from audit_svc.models import Alerta, Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        agora = datetime.now(timezone.utc)
        for ip in ("10.0.0.5", "192.168.1.2", "203.0.113.20"):
            db.add(Alerta(regra="rajada", severidade="alta", ip=ip, descricao="x", criado_em=agora, status="confirmado"))
        db.commit()
        assert [o["pattern"] for o in cti.objetos(db)] == ["[ipv4-addr:value = '203.0.113.20']"]
