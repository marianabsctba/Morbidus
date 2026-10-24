import pytest
from fastapi.testclient import TestClient
from identity_svc.config import IdentitySettings
from identity_svc.main import build_app

ADMIN = {"X-Admin-Token": "segredo-admin"}


@pytest.fixture
def client():
    settings = IdentitySettings(database_url="sqlite:///:memory:", admin_token="segredo-admin", api_keys_habilitadas=True)
    with TestClient(build_app(settings)) as c:
        yield c


def _tenant_e_chave(client):
    tenant = client.post("/v1/admin/tenants", json={"nome": "Banco Exemplo"}, headers=ADMIN).json()
    key = client.post(f"/v1/admin/tenants/{tenant['id']}/api-keys", json={"nome": "prod"}, headers=ADMIN)
    assert key.status_code == 201
    return tenant, key.json()


def test_admin_exige_token(client):
    assert client.post("/v1/admin/tenants", json={"nome": "X Y"}).status_code == 403
    assert client.post("/v1/admin/tenants", json={"nome": "X Y"}, headers={"X-Admin-Token": "errado"}).status_code == 403


def test_verify_aceita_chave_valida_e_injeta_tenant(client):
    tenant, key = _tenant_e_chave(client)
    resp = client.get("/auth/verify", headers={"X-API-Key": key["chave"]})
    assert resp.status_code == 200
    assert resp.headers["X-Tenant-Id"] == tenant["id"]
    assert resp.headers["X-Api-Key-Id"] == key["id"]


def test_verify_recusa_chave_adulterada_e_revogada(client):
    _, key = _tenant_e_chave(client)
    assert client.get("/auth/verify", headers={"X-API-Key": key["chave"] + "x"}).status_code == 401
    assert client.get("/auth/verify").status_code == 401
    assert client.delete(f"/v1/admin/api-keys/{key['id']}", headers=ADMIN).status_code == 204
    assert client.get("/auth/verify", headers={"X-API-Key": key["chave"]}).status_code == 401
