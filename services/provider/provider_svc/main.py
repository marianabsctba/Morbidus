"""provider-svc: consulta síncrona de CPF nos provedores oficiais de óbito."""

import asyncio
import logging

from fastapi import HTTPException
from morbidus_common.logging import setup_logging
from morbidus_common.text import is_valid_cpf, only_digits
from morbidus_common.web import create_app
from pydantic import BaseModel

from provider_svc.config import ProviderSettings
from provider_svc.providers import DeathProvider, ProviderResult, ProviderStatus, build_providers
from provider_svc.resilience import CircuitBreaker, TTLCache

log = logging.getLogger(__name__)


class LookupIn(BaseModel):
    cpf: str


class LookupOut(BaseModel):
    resultados: list[ProviderResult]


def build_app(settings: ProviderSettings | None = None, providers: list[DeathProvider] | None = None):
    settings = settings or ProviderSettings()
    setup_logging("provider", settings.log_level)
    providers = providers if providers is not None else build_providers(
        settings.enabled_providers, settings.mock_deceased_bases
    )
    cache = TTLCache(settings.cache_ttl_seconds)
    breakers = {
        p.name: CircuitBreaker(settings.breaker_failures, settings.breaker_reset_seconds) for p in providers
    }

    app = create_app("provider", "Conectores para provedores oficiais de óbito (CPF).")

    async def _lookup(provider: DeathProvider, cpf: str) -> ProviderResult:
        cache_key = f"{provider.name}:{cpf}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        breaker = breakers[provider.name]
        if breaker.is_open:
            return ProviderResult(provider=provider.name, status=ProviderStatus.INDISPONIVEL, detalhe="circuito aberto")
        try:
            result = await asyncio.wait_for(provider.lookup(cpf), settings.provider_timeout_seconds)
        except Exception:
            log.exception("falha no provedor %s", provider.name)
            breaker.record_failure()
            return ProviderResult(provider=provider.name, status=ProviderStatus.INDISPONIVEL, detalhe="falha na consulta")
        breaker.record_success()
        cache.set(cache_key, result)
        return result

    @app.post("/v1/lookup", response_model=LookupOut)
    async def lookup(body: LookupIn):
        cpf = only_digits(body.cpf)
        if not is_valid_cpf(cpf):
            raise HTTPException(status_code=422, detail="CPF inválido")
        resultados = await asyncio.gather(*(_lookup(p, cpf) for p in providers))
        return LookupOut(resultados=list(resultados))

    return app
