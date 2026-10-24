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


def _consulta(tenant="t1", minuto=0, nome=None, status=QueryStatus.SEM_REGISTRO, dias=None, ip="203.0.113.9", n=0):
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
