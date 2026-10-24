"""identity-svc: contas, sessões, API keys e a verificação usada pelo forwardAuth do gateway."""

import hmac
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Cookie, Depends, Header, HTTPException, Response
from morbidus_common.db import make_engine, utcnow
from morbidus_common.logging import setup_logging
from morbidus_common.web import create_app
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from identity_svc.config import IdentitySettings
from identity_svc.contas import apaga_mfa, build_router, eh_admin_efetivo, hoje, limite_do_tenant, usuario_da_sessao
from identity_svc.keys import generate_key, hash_key, parse_prefix
from identity_svc.models import Administrador, ApiKey, Base, Tenant, UsoDiario, Usuario


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


class UsuarioAdminOut(BaseModel):
    email: str
    nome: str
    organizacao: str | None
    uso_pretendido: str
    email_verificado: bool
    ativo: bool
    limite_diario: int | None
    criado_em: datetime


class UsuarioAdminIn(BaseModel):
    ativo: bool | None = None
    email_verificado: bool | None = None
    # 0 libera consultas ilimitadas; nulo volta ao padrão.
    limite_diario: int | None = Field(default=None, ge=0)
    admin: bool | None = None
    resetar_mfa: bool | None = None


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

    @app.get("/v1/admin/usuarios", response_model=list[UsuarioAdminOut], dependencies=admin)
    def list_usuarios(db: Session = Depends(get_db)):
        return db.scalars(select(Usuario).order_by(Usuario.criado_em)).all()

    @app.patch("/v1/admin/usuarios/{email}", response_model=UsuarioAdminOut, dependencies=admin)
    def update_usuario(email: str, body: UsuarioAdminIn, db: Session = Depends(get_db)):
        usuario = db.scalar(select(Usuario).where(Usuario.email == email.lower()))
        if not usuario:
            raise HTTPException(status_code=404, detail="usuário não encontrado")
        mudancas = body.model_dump(exclude_unset=True)
        admin = mudancas.pop("admin", None)
        if mudancas.pop("resetar_mfa", None):
            apaga_mfa(db, usuario.id)
        for campo, valor in mudancas.items():
            setattr(usuario, campo, valor)
        atual = db.get(Administrador, usuario.id)
        if admin and atual is None:
            db.add(Administrador(usuario_id=usuario.id))
        elif admin is False and atual is not None:
            db.delete(atual)
        db.commit()
        return usuario

    app.include_router(build_router(settings, get_db))

    @app.post("/interno/emails", include_in_schema=False)
    def emails_por_tenant(tenants: list[str], db: Session = Depends(get_db)) -> dict[str, str]:
        """Para o audit-svc avisar instituições sobre identidade quente. Rota interna."""
        usuarios = db.scalars(select(Usuario).where(Usuario.tenant_id.in_(tenants[:200]), Usuario.ativo.is_(True)))
        return {u.tenant_id: u.email for u in usuarios}

    @app.get("/interno/admins", include_in_schema=False)
    def emails_admins(db: Session = Depends(get_db)) -> list[str]:
        """Para o audit-svc avisar sobre alertas. Rota interna: o gateway não a expõe."""
        ids = db.scalars(select(Administrador.usuario_id))
        usuarios = [db.get(Usuario, i) for i in ids]
        return [u.email for u in usuarios if u is not None and u.ativo]

    @app.get("/auth/verify", include_in_schema=False)
    def verify(
        x_api_key: str | None = Header(default=None),
        x_forwarded_method: str | None = Header(default=None),
        x_forwarded_uri: str | None = Header(default=None),
        mbd_sessao: str | None = Cookie(default=None),
        db: Session = Depends(get_db),
    ):
        """forwardAuth do gateway: aceita API key ou sessão do painel e aplica a cota diária."""
        key_id = ""
        if x_api_key and not settings.api_keys_habilitadas:
            raise HTTPException(status_code=401, detail="acesso por API desativado; use o painel")
        if x_api_key:
            prefixo = parse_prefix(x_api_key)
            key = db.scalar(select(ApiKey).where(ApiKey.prefixo == prefixo)) if prefixo else None
            if (
                key is None
                or key.revogada_em is not None
                or not hmac.compare_digest(key.hash, hash_key(x_api_key, settings.api_key_pepper))
            ):
                raise HTTPException(status_code=401, detail="API key inválida")
            tenant_id, key_id = key.tenant_id, key.id
            usuario = db.scalar(select(Usuario).where(Usuario.tenant_id == tenant_id))
            if usuario is not None and not usuario.email_verificado:
                raise HTTPException(status_code=403, detail="conta aguardando liberação")
            if usuario is not None and not usuario.ativo:
                raise HTTPException(status_code=403, detail="conta desativada")
        else:
            usuario = usuario_da_sessao(db, mbd_sessao)
            if usuario is None:
                raise HTTPException(status_code=401, detail="faça login para continuar")
            tenant_id = usuario.tenant_id
        tenant = db.get(Tenant, tenant_id)
        if not tenant or not tenant.ativo:
            raise HTTPException(status_code=403, detail="tenant inativo")

        if x_forwarded_method == "POST" and (x_forwarded_uri or "").startswith("/v1/consultas"):
            limite = limite_do_tenant(db, settings, tenant_id)
            uso = db.get(UsoDiario, (tenant_id, hoje())) or UsoDiario(tenant_id=tenant_id, dia=hoje(), consultas=0)
            if limite > 0 and uso.consultas >= limite:
                raise HTTPException(status_code=429, detail=f"limite diário de {limite} consultas atingido")
            uso.consultas += 1
            db.merge(uso)
            db.commit()

        papel = "admin" if usuario is not None and eh_admin_efetivo(db, usuario.id) else ""
        # Sempre devolve todos os cabeçalhos, para o gateway sobrescrever o que o cliente mandar.
        return Response(
            status_code=200, headers={"X-Tenant-Id": tenant.id, "X-Api-Key-Id": key_id, "X-Papel": papel}
        )

    return app
