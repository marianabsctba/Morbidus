"""Fluxo completo em um processo: crawler, resolver, query e audit no mesmo barramento em memória."""

import httpx
from audit_svc.config import AuditSettings
from audit_svc.main import build_app as build_audit
from crawler_svc.config import CrawlerSettings
from crawler_svc.main import build_app as build_crawler
from fastapi.testclient import TestClient
from morbidus_common.bus import InMemoryBus
from morbidus_common.search import InMemoryDeathIndex
from morbidus_common.text import cpf_with_check_digits
from provider_svc.config import ProviderSettings
from provider_svc.main import build_app as build_provider
from query_svc.config import QuerySettings
from query_svc.main import build_app as build_query
from resolver_svc.config import ResolverSettings
from resolver_svc.main import build_app as build_resolver

TENANT = {"X-Tenant-Id": "banco-exemplo"}


def test_obituario_coletado_vira_sinal_e_fica_auditado():
    bus, index = InMemoryBus(), InMemoryDeathIndex()
    provider = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=build_provider(ProviderSettings())), base_url="http://provider"
    )
    crawler = TestClient(build_crawler(CrawlerSettings(enabled_spiders="fixture"), bus=bus))
    resolver = TestClient(build_resolver(ResolverSettings(database_url="sqlite:///:memory:"), bus=bus, index=index))
    audit_app = build_audit(AuditSettings(database_url="sqlite:///:memory:"), bus=bus)
    audit_http = httpx.AsyncClient(transport=httpx.ASGITransport(app=audit_app), base_url="http://audit")
    query = TestClient(
        build_query(QuerySettings(), bus=bus, index=index, provider_client=provider, audit_client=audit_http)
    )
    audit = TestClient(audit_app)

    with crawler, resolver, query, audit:
        coleta = crawler.post("/v1/sources/fixture/run").json()
        assert coleta["entradas_publicadas"] == 3
        assert len(index.docs) == 3

        por_nome = query.post(
            "/v1/consultas",
            json={
                "nome": "Beltrana Fictícia Souza",
                "cidade": "Curitiba",
                "uf": "PR",
                "data_nascimento": "1959-02-01",
                "finalidade": "onboarding",
            },
            headers=TENANT,
        ).json()
        assert por_nome["status"] == "sinal_forte"
        assert por_nome["evidencias"][0]["detalhes"]["idade"] == 67

        por_cpf = query.post(
            "/v1/consultas",
            json={"cpf": cpf_with_check_digits("529982247"), "finalidade": "concessao_credito"},
            headers=TENANT,
        ).json()
        assert por_cpf["status"] == "obito_confirmado"

        trilha = audit.get("/v1/auditoria", headers=TENANT).json()
        assert {e["status"] for e in trilha} == {"sinal_forte", "obito_confirmado"}

        # Mais duas instituições batendo na mesma pessoa: cada uma vê quantas outras já bateram.
        busca = {"nome": "Beltrana Fictícia Souza", "cidade": "Curitiba", "uf": "PR", "finalidade": "onboarding"}
        segunda = query.post("/v1/consultas", json=busca, headers={"X-Tenant-Id": "coop-2"}).json()
        assert segunda["alerta_coletivo"] is None  # só 1 outra instituição: abaixo do limite
        terceira = query.post("/v1/consultas", json=busca, headers={"X-Tenant-Id": "coop-3"}).json()
        assert terceira["alerta_coletivo"]["outras_instituicoes"] == 2
