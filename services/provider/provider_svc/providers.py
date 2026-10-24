"""Contrato dos provedores oficiais de óbito e as implementações disponíveis."""

from abc import ABC, abstractmethod
from datetime import date
from enum import Enum

from morbidus_common.text import cpf_with_check_digits
from pydantic import BaseModel


class ProviderStatus(str, Enum):
    FALECIDO = "falecido"
    REGULAR = "regular"
    DESCONHECIDO = "desconhecido"
    INDISPONIVEL = "indisponivel"


class ProviderResult(BaseModel):
    provider: str
    status: ProviderStatus
    data_obito: date | None = None
    ano_obito: int | None = None
    detalhe: str | None = None


class DeathProvider(ABC):
    name: str

    @abstractmethod
    async def lookup(self, cpf: str) -> ProviderResult:
        """Recebe CPF só com dígitos e já validado."""


class MockProvider(DeathProvider):
    """Provedor fictício para desenvolvimento e testes. Nunca habilitar em produção."""

    name = "mock"

    def __init__(self, deceased_bases: list[str]) -> None:
        self._deceased = {cpf_with_check_digits(b) for b in deceased_bases if len(b) == 9}

    async def lookup(self, cpf: str) -> ProviderResult:
        if cpf in self._deceased:
            return ProviderResult(provider=self.name, status=ProviderStatus.FALECIDO, ano_obito=2023)
        return ProviderResult(provider=self.name, status=ProviderStatus.REGULAR)


def build_providers(enabled: str, mock_deceased_bases: str) -> list[DeathProvider]:
    available = {
        "mock": lambda: MockProvider([b.strip() for b in mock_deceased_bases.split(",")]),
    }
    providers = []
    for name in (n.strip() for n in enabled.split(",") if n.strip()):
        if name not in available:
            raise ValueError(f"provedor desconhecido: {name}")
        providers.append(available[name]())
    return providers
