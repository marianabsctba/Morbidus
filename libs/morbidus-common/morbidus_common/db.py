from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_columns(engine: Engine, table: str, columns: dict[str, str]) -> list[str]:
    """Acrescenta colunas novas a uma tabela que já existe (create_all não faz isso).

    Só adiciona; nunca altera nem remove. `columns` mapeia nome para o tipo SQL.
    """
    existentes = {c["name"] for c in inspect(engine).get_columns(table)}
    faltando = [nome for nome in columns if nome not in existentes]
    with engine.begin() as conn:
        for nome in faltando:
            conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {nome} {columns[nome]}'))
    return faltando


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
        return create_engine(url, **kwargs)
    return create_engine(url, pool_pre_ping=True)
