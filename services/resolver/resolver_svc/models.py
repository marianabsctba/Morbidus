from datetime import date, datetime
from uuid import uuid4

from morbidus_common.db import utcnow
from sqlalchemy import JSON, Date, DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DeathRecord(Base):
    __tablename__ = "death_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid4().hex)
    nome: Mapped[str] = mapped_column(String(300))
    nome_normalizado: Mapped[str] = mapped_column(String(300))
    chave_fonetica: Mapped[str] = mapped_column(String(200), index=True)
    idade: Mapped[int | None]
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    data_falecimento: Mapped[date | None] = mapped_column(Date)
    ano_nascimento_estimado: Mapped[int | None]
    cidade: Mapped[str] = mapped_column(String(120))
    uf: Mapped[str] = mapped_column(String(2), index=True)
    fontes: Mapped[list] = mapped_column(JSON, default=list)
    # Pessoa fictícia plantada para detectar vazamento (resolver_svc/canarios.py).
    canario: Mapped[bool] = mapped_column(default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ProcessedEvent(Base):
    """Garante idempotência: o Kafka entrega pelo menos uma vez."""

    __tablename__ = "processed_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    processado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
