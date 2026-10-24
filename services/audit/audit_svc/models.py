from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, String, text
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
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            for stmt in _APPEND_ONLY:
                conn.execute(text(stmt))
