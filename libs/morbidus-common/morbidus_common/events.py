"""Contratos dos eventos trafegados no Kafka. Mudou o contrato, sobe o schema_version."""

from datetime import date, datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class Topics:
    OBITUARY_RAW = "obituary.raw"
    DEATH_RECORD_NORMALIZED = "death.record.normalized"
    QUERY_PERFORMED = "query.performed"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Event(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    occurred_at: datetime = Field(default_factory=_now)
    schema_version: int = 1


class ObituaryRaw(Event):
    """Entrada extraída de uma página de obituário, ainda sem normalização.

    Só carrega dados do falecido: nomes de parentes nunca são extraídos (LGPD).
    """

    source_id: str
    source_url: str
    cidade: str
    uf: str
    nome: str
    idade: str | None = None
    data_nascimento: str | None = None
    data_falecimento: str | None = None
    data_sepultamento: str | None = None
    local: str | None = None
    raw_object_key: str | None = None


class DeathRecordNormalized(Event):
    record_id: str
    nome: str
    nome_normalizado: str
    chave_fonetica: str
    idade: int | None = None
    data_nascimento: date | None = None
    data_falecimento: date | None = None
    ano_nascimento_estimado: int | None = None
    cidade: str
    uf: str
    fontes: list[str]
    # Pessoa fictícia plantada na base para detectar vazamento (ver resolver_svc/canarios.py).
    canario: bool = False


class QueryStatus(str, Enum):
    OBITO_CONFIRMADO = "obito_confirmado"
    SINAL_FORTE = "sinal_forte"
    SINAL_FRACO = "sinal_fraco"
    SEM_REGISTRO = "sem_registro"


class QueryPerformed(Event):
    query_id: str
    tenant_id: str
    api_key_id: str | None = None
    finalidade: str
    cpf_mascarado: str | None = None
    cpf_hash: str | None = None
    nome_consultado: str | None = None
    status: QueryStatus
    score: float
    fontes_consultadas: list[str]
    # Registro de acesso (Marco Civil, art. 15). Só a administração vê.
    ip_origem: str | None = None
    user_agent: str | None = None
    # Há quantos dias morreu a pessoa do obituário mais recente encontrado.
    # Usado pelo detector de abuso: caçar óbitos recentes é padrão de fraudador.
    dias_desde_obito: int | None = None
    # Identidades que bateram com acerto forte: "registro:<id>" (obituário) ou
    # "cpf:<hash>" (fonte oficial). Base da "identidade quente".
    identidades: list[str] = Field(default_factory=list)
    # A consulta bateu numa identidade-canário: o nome veio de fora do MORBiDus.
    canario: bool = False
