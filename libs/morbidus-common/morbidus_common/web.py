"""Fábrica de apps FastAPI e dependências comuns (tenant vindo do gateway)."""

from dataclasses import dataclass

from fastapi import Depends, FastAPI, Header, HTTPException

BRAND = "MORBiDus"
TAGLINE = "Dead identities. Living fraud."


def create_app(service: str, description: str, lifespan=None) -> FastAPI:
    app = FastAPI(
        title=f"{BRAND} {service}",
        description=f"{TAGLINE} Death Identity Fraud Prevention (DIFP). {description}",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health", tags=["infra"])
    def health() -> dict:
        return {"status": "ok", "service": service}

    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app, include_in_schema=False)
    return app


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    api_key_id: str | None
    admin: bool = False


def require_tenant(
    x_tenant_id: str | None = Header(default=None),
    x_api_key_id: str | None = Header(default=None),
    x_papel: str | None = Header(default=None),
) -> TenantContext:
    """O gateway injeta esses headers depois de validar a API key no identity-svc.

    Os serviços não ficam expostos fora da rede interna; a checagem aqui é
    defesa em profundidade para chamadas que cheguem sem passar pelo gateway.
    """
    if not x_tenant_id:
        raise HTTPException(status_code=401, detail="tenant não identificado")
    # Consulta feita pelo painel (sessão) chega com X-Api-Key-Id vazio.
    return TenantContext(tenant_id=x_tenant_id, api_key_id=x_api_key_id or None, admin=x_papel == "admin")


def require_admin(tenant: TenantContext = Depends(require_tenant)) -> TenantContext:
    """X-Papel vem do forwardAuth do gateway, que sobrescreve qualquer valor enviado pelo cliente."""
    if not tenant.admin:
        raise HTTPException(status_code=403, detail="acesso restrito à administração")
    return tenant
