"""Sobe a plataforma inteira em um processo, sem Docker, para desenvolver o painel.

    python scripts/dev_stack.py          # http://localhost:8080

Faz o papel do Traefik: valida a API key no identity-svc e injeta X-Tenant-Id.
O índice de busca é carregado da base local montada por scripts/coletar.py.
Crie a conta pelo próprio painel; sem SMTP, libere-a com
PATCH /v1/admin/usuarios/<email> (X-Admin-Token). Não use em produção.
"""

import asyncio
import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
for servico in ("identity", "provider", "crawler", "resolver", "query", "audit"):
    sys.path.insert(0, str(RAIZ / "services" / servico))

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from audit_svc.config import AuditSettings  # noqa: E402
from audit_svc.main import build_app as build_audit  # noqa: E402
from crawler_svc.config import CrawlerSettings  # noqa: E402
from crawler_svc.main import build_app as build_crawler  # noqa: E402
from identity_svc.config import IdentitySettings  # noqa: E402
from identity_svc.main import build_app as build_identity  # noqa: E402
from morbidus_common.bus import InMemoryBus  # noqa: E402
from morbidus_common.search import InMemoryDeathIndex  # noqa: E402
from provider_svc.config import ProviderSettings  # noqa: E402
from provider_svc.main import build_app as build_provider  # noqa: E402
from query_svc.config import QuerySettings  # noqa: E402
from query_svc.main import build_app as build_query  # noqa: E402
from resolver_svc.config import ResolverSettings  # noqa: E402
from resolver_svc.main import build_app as build_resolver  # noqa: E402
from resolver_svc.models import DeathRecord  # noqa: E402
from resolver_svc.resolver import to_event  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import FileResponse, JSONResponse, Response  # noqa: E402
from starlette.routing import Route  # noqa: E402

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "dev-admin")
BASE_LOCAL = f"sqlite:///{RAIZ / 'morbidus_local.db'}"
WEB_DIST = RAIZ / "web" / "dist"

bus, index = InMemoryBus(), InMemoryDeathIndex()
provider = build_provider(ProviderSettings())
apps = {
    "identity": build_identity(
        IdentitySettings(
            database_url=f"sqlite:///{RAIZ / 'dev_identity.db'}", admin_token=ADMIN_TOKEN, smtp_host=""
        )
    ),
    "query": build_query(
        QuerySettings(),
        bus=bus,
        index=index,
        provider_client=httpx.AsyncClient(transport=httpx.ASGITransport(app=provider), base_url="http://provider"),
    ),
    "resolver": build_resolver(ResolverSettings(database_url=BASE_LOCAL), bus=bus, index=index),
    "audit": build_audit(AuditSettings(database_url=f"sqlite:///{RAIZ / 'dev_audit.db'}"), bus=bus),
    "crawler": build_crawler(CrawlerSettings(enabled_spiders="all"), bus=bus),
    "provider": provider,
}
clients = {
    nome: httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=f"http://{nome}") for nome, app in apps.items()
}

# (prefixo, serviço, exige API key, métodos permitidos). Mesmas regras do docker-compose.
ROTAS = [
    ("/v1/admin", "identity", False, None),
    ("/v1/conta", "identity", False, None),
    ("/v1/sessao", "identity", False, None),
    ("/v1/consultas", "query", True, {"POST"}),
    ("/v1/auditoria", "audit", True, {"GET"}),
    ("/v1/alertas", "audit", True, {"GET", "PATCH"}),
    ("/v1/cti", "audit", True, {"GET"}),
    ("/taxii2", "audit", False, {"GET"}),
    ("/v1/estatisticas", "resolver", True, {"GET"}),
    ("/v1/canarios", "resolver", True, {"GET", "POST"}),
    ("/v1/sources", "crawler", True, {"GET"}),
]
_SEM_REPASSE = {"host", "content-length", "x-tenant-id", "x-api-key-id", "x-papel", "x-real-ip", "x-forwarded-for", "transfer-encoding", "content-encoding"}


async def gateway(request: Request) -> Response:
    caminho = request.url.path
    rota = next((r for r in ROTAS if caminho.startswith(r[0])), None)
    if rota is None:
        return _web(caminho)
    _, servico, exige_chave, metodos = rota
    if metodos and request.method not in metodos:
        return JSONResponse({"detail": "método não permitido"}, status_code=405)
    headers = {k: v for k, v in request.headers.items() if k.lower() not in _SEM_REPASSE}
    # Como o Traefik sem proxy confiável na frente: o IP é o da conexão, nunca o do cliente.
    headers["X-Real-Ip"] = request.client.host if request.client else ""
    if exige_chave:
        # Mesmo contrato do forwardAuth do Traefik: credenciais + método e URI originais.
        auth_headers = {"X-Forwarded-Method": request.method, "X-Forwarded-Uri": caminho}
        for nome in ("x-api-key", "cookie"):
            if nome in request.headers:
                auth_headers[nome] = request.headers[nome]
        auth = await clients["identity"].get("/auth/verify", headers=auth_headers)
        if auth.status_code != 200:
            return JSONResponse(auth.json(), status_code=auth.status_code)
        headers["X-Tenant-Id"] = auth.headers["x-tenant-id"]
        headers["X-Api-Key-Id"] = auth.headers["x-api-key-id"]
        headers["X-Papel"] = auth.headers.get("x-papel", "")
    resp = await clients[servico].request(
        request.method, caminho, params=request.query_params, headers=headers, content=await request.body()
    )
    saida = Response(resp.content, status_code=resp.status_code)
    for k, v in resp.headers.multi_items():
        if k.lower() not in _SEM_REPASSE:
            saida.headers.append(k, v)
    return saida


def _web(caminho: str) -> Response:
    if not WEB_DIST.exists():
        return JSONResponse({"detail": "painel não compilado: rode npm run build em web/"}, status_code=404)
    arquivo = (WEB_DIST / caminho.lstrip("/")).resolve()
    if arquivo.is_file() and WEB_DIST in arquivo.parents:
        return FileResponse(arquivo)
    return FileResponse(WEB_DIST / "index.html")


_ultima_carga = None


def _carregar_indice() -> int:
    """Carrega o que mudou desde a última carga; o coletar.py pode estar gravando em paralelo."""
    global _ultima_carga
    engine = create_engine(BASE_LOCAL)
    with Session(engine) as db:
        consulta = select(DeathRecord)
        if _ultima_carga is not None:
            consulta = consulta.where(DeathRecord.atualizado_em > _ultima_carga)
        for rec in db.scalars(consulta):
            index.upsert(to_event(rec))
            _ultima_carga = max(_ultima_carga or rec.atualizado_em, rec.atualizado_em)
    engine.dispose()
    return len(index.docs)


async def _recarregar_periodicamente() -> None:
    while True:
        await asyncio.sleep(60)
        await asyncio.to_thread(_carregar_indice)


@asynccontextmanager
async def lifespan(app):
    async with AsyncExitStack() as stack:
        for sub in apps.values():
            await stack.enter_async_context(sub.router.lifespan_context(sub))
        print(f"Índice carregado com {_carregar_indice()} registros da base local")
        recarga = asyncio.create_task(_recarregar_periodicamente())
        yield
        recarga.cancel()


app = Starlette(
    routes=[Route("/{caminho:path}", gateway, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])],
    lifespan=lifespan,
)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8080")))
