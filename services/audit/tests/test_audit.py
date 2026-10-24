from fastapi.testclient import TestClient
from audit_svc.config import AuditSettings
from audit_svc.main import build_app
from morbidus_common.bus import InMemoryBus
from morbidus_common.events import QueryPerformed, QueryStatus, Topics


def _evento(tenant, query_id):
    return QueryPerformed(
        query_id=query_id,
        tenant_id=tenant,
        finalidade="onboarding",
        cpf_mascarado="***.444.777-**",
        status=QueryStatus.SEM_REGISTRO,
        score=0.0,
        fontes_consultadas=["oficial"],
    )


async def test_auditoria_isolada_por_tenant_e_idempotente():
    bus = InMemoryBus()
    with TestClient(build_app(AuditSettings(database_url="sqlite:///:memory:"), bus=bus)) as client:
        repetido = _evento("t1", "q1")
        await bus.publish(Topics.QUERY_PERFORMED, repetido)
        await bus.publish(Topics.QUERY_PERFORMED, repetido)
        await bus.publish(Topics.QUERY_PERFORMED, _evento("t2", "q2"))

        t1 = client.get("/v1/auditoria", headers={"X-Tenant-Id": "t1"}).json()
        assert [e["query_id"] for e in t1] == ["q1"]
        assert client.get("/v1/auditoria").status_code == 401


async def test_auditoria_geral_so_para_admin():
    bus = InMemoryBus()
    with TestClient(build_app(AuditSettings(database_url="sqlite:///:memory:"), bus=bus)) as client:
        await bus.publish(Topics.QUERY_PERFORMED, _evento("t1", "q1"))
        await bus.publish(Topics.QUERY_PERFORMED, _evento("t2", "q2"))
        assert client.get("/v1/auditoria/geral", headers={"X-Tenant-Id": "t1"}).status_code == 403
        geral = client.get("/v1/auditoria/geral", headers={"X-Tenant-Id": "t1", "X-Papel": "admin"}).json()
        assert {e["tenant_id"] for e in geral} == {"t1", "t2"}
        filtrado = client.get("/v1/auditoria/geral?tenant_id=t2", headers={"X-Tenant-Id": "t1", "X-Papel": "admin"}).json()
        assert [e["query_id"] for e in filtrado] == ["q2"]


async def test_ip_so_na_auditoria_geral_e_migracao_de_coluna(tmp_path):
    from sqlalchemy import create_engine, text

    url = f"sqlite:///{tmp_path / 'audit.db'}"
    antigo = create_engine(url)
    with antigo.begin() as conn:
        # Tabela como estava em produção, antes das colunas de IP.
        conn.execute(text(
            "CREATE TABLE audit_entries (event_id VARCHAR(64) PRIMARY KEY, query_id VARCHAR(32), tenant_id VARCHAR(32),"
            " api_key_id VARCHAR(32), finalidade VARCHAR(40), cpf_mascarado VARCHAR(20), cpf_hash VARCHAR(64),"
            " nome_consultado VARCHAR(300), status VARCHAR(30), score FLOAT, fontes_consultadas JSON, ocorrido_em DATETIME)"
        ))
    antigo.dispose()

    bus = InMemoryBus()
    with TestClient(build_app(AuditSettings(database_url=url), bus=bus)) as client:
        evento = _evento("t1", "q1")
        evento.ip_origem, evento.user_agent = "203.0.113.9", "Navegador Teste/1.0"
        await bus.publish(Topics.QUERY_PERFORMED, evento)
        assert "ip_origem" not in client.get("/v1/auditoria", headers={"X-Tenant-Id": "t1"}).json()[0]
        admin = {"X-Tenant-Id": "t1", "X-Papel": "admin"}
        geral = client.get("/v1/auditoria/geral", headers=admin).json()
        assert geral[0]["ip_origem"] == "203.0.113.9" and geral[0]["user_agent"] == "Navegador Teste/1.0"
        assert client.get("/v1/auditoria/geral?ip=198.51.100.1", headers=admin).json() == []
