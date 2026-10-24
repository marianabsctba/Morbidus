"""identity-svc: tenants, API keys e a verificação usada pelo forwardAuth do gateway."""

import hmac
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, Header, HTTPException, Response
from morbidus_common.db import make_engine, utcnow
from morbidus_common.logging import setup_logging
from morbidus_common.web import create_app
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from identity_svc.config import IdentitySettings
from identity_svc.keys import generate_key, hash_key, parse_prefix
from identity_svc.models import ApiKey, Base, Tenant


class TenantIn(BaseModel):
    nome: str = Field(min_length=2, max_length=200)


class TenantOut(BaseModel):
    id: str
    nome: str
    ativo: bool
    criado_em: datetime


class ApiKeyIn(BaseModel):
    nome: str = Field(min_length=2, max_length=200)


class ApiKeyCreated(BaseModel):
    id: str
    prefixo: str
    chave: str = Field(description="Exibida uma única vez; guarde em local seguro.")


def build_app(settings: IdentitySettings | None = None):
    settings = settings or IdentitySettings()
    setup_logging("identity", settings.log_level)
    engine = make_engine(settings.database_url)
    SessionLocal = sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(app):
        Base.metadata.create_all(engine)
        yield
        engine.dispose()

    app = create_app("identity", "Tenants, API keys e autenticação.", lifespan)

    def get_db():
        with SessionLocal() as session:
            yield session

    def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
        if not settings.admin_token or not x_admin_token:
            raise HTTPException(status_code=403, detail="acesso administrativo negado")
        if not hmac.compare_digest(x_admin_token, settings.admin_token):
            raise HTTPException(status_code=403, detail="acesso administrativo negado")

    admin = [Depends(require_admin)]

    @app.post("/v1/admin/tenants", response_model=TenantOut, status_code=201, dependencies=admin)
    def create_tenant(body: TenantIn, db: Session = Depends(get_db)):
        tenant = Tenant(nome=body.nome)
        db.add(tenant)
        db.commit()
        return tenant

    @app.get("/v1/admin/tenants", response_model=list[TenantOut], dependencies=admin)
    def list_tenants(db: Session = Depends(get_db)):
        return db.scalars(select(Tenant).order_by(Tenant.criado_em)).all()

    @app.post(
        "/v1/admin/tenants/{tenant_id}/api-keys",
        response_model=ApiKeyCreated,
        status_code=201,
        dependencies=admin,
    )
    def create_api_key(tenant_id: str, body: ApiKeyIn, db: Session = Depends(get_db)):
        if not db.get(Tenant, tenant_id):
            raise HTTPException(status_code=404, detail="tenant não encontrado")
        chave, prefixo, digest = generate_key(settings.api_key_pepper)
        key = ApiKey(tenant_id=tenant_id, nome=body.nome, prefixo=prefixo, hash=digest)
        db.add(key)
        db.commit()
        return ApiKeyCreated(id=key.id, prefixo=prefixo, chave=chave)

    @app.delete("/v1/admin/api-keys/{key_id}", status_code=204, dependencies=admin)
    def revoke_api_key(key_id: str, db: Session = Depends(get_db)):
        key = db.get(ApiKey, key_id)
        if not key:
            raise HTTPException(status_code=404, detail="API key não encontrada")
        key.revogada_em = key.revogada_em or utcnow()
        db.commit()

    @app.get("/auth/verify", include_in_schema=False)
    def verify(x_api_key: str | None = Header(default=None), db: Session = Depends(get_db)):
        prefixo = parse_prefix(x_api_key) if x_api_key else None
        key = db.scalar(select(ApiKey).where(ApiKey.prefixo == prefixo)) if prefixo else None
        if (
            key is None
            or key.revogada_em is not None
            or not hmac.compare_digest(key.hash, hash_key(x_api_key, settings.api_key_pepper))
        ):
            raise HTTPException(status_code=401, detail="API key inválida")
        tenant = db.get(Tenant, key.tenant_id)
        if not tenant or not tenant.ativo:
            raise HTTPException(status_code=403, detail="tenant inativo")
        return Response(status_code=200, headers={"X-Tenant-Id": tenant.id, "X-Api-Key-Id": key.id})

    return app
