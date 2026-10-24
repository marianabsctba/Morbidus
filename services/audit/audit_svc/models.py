from datetime import datetime
from uuid import uuid4

from morbidus_common.db import ensure_columns
from sqlalchemy import JSON, DateTime, Float, Integer, String, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    query_id: Mapped[str] = mapped_column(String(32), index=True)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    api_key_id: Mapped[str | None] = mapped_column(String(32))
    finalidade: Mapped[str] = mapped_column(String(40))
    cpf_mascarado: Mapped[str | None] = mapped_column(String(20))
    cpf_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    nome_consultado: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(30))
    score: Mapped[float] = mapped_column(Float)
    fontes_consultadas: Mapped[list] = mapped_column(JSON)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # Registro de acesso (Marco Civil, art. 15). Exposto só na auditoria geral.
    ip_origem: Mapped[str | None] = mapped_column(String(45), index=True)
    user_agent: Mapped[str | None] = mapped_column(String(300))
    dias_desde_obito: Mapped[int | None] = mapped_column(Integer)


class Alerta(Base):
    """Suspeita de abuso aberta pelo detector (audit_svc/sentinela.py)."""

    __tablename__ = "alertas"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid4().hex)
    regra: Mapped[str] = mapped_column(String(40), index=True)
    severidade: Mapped[str] = mapped_column(String(10))
    tenant_id: Mapped[str | None] = mapped_column(String(32), index=True)
    ip: Mapped[str | None] = mapped_column(String(45), index=True)
    descricao: Mapped[str] = mapped_column(String(300))
    evidencias: Mapped[dict] = mapped_column(JSON, default=dict)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(15), default="aberto", index=True)
    resolvido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


# Colunas acrescentadas depois que a tabela já existia em produção.
_COLUNAS_NOVAS = {"ip_origem": "VARCHAR(45)", "user_agent": "VARCHAR(300)", "dias_desde_obito": "INTEGER"}

_APPEND_ONLY = [
    """
    CREATE OR REPLACE FUNCTION audit_block_mutation() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'audit_entries é append-only';
    END;
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS audit_no_mutation ON audit_entries",
    """
    CREATE TRIGGER audit_no_mutation BEFORE UPDATE OR DELETE ON audit_entries
    FOR EACH ROW EXECUTE FUNCTION audit_block_mutation()
    """,
]


def setup_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    ensure_columns(engine, "audit_entries", _COLUNAS_NOVAS)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            for stmt in _APPEND_ONLY:
                conn.execute(text(stmt))
