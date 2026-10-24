from datetime import date, datetime
from uuid import uuid4

from morbidus_common.db import utcnow
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _id() -> str:
    return uuid4().hex


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    nome: Mapped[str] = mapped_column(String(200))
    ativo: Mapped[bool] = mapped_column(default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    nome: Mapped[str] = mapped_column(String(200))
    prefixo: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    hash: Mapped[str] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revogada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class Usuario(Base):
    """Conta criada pelo cadastro do site. Cada usuário tem um tenant próprio."""

    __tablename__ = "usuarios"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), unique=True)
    nome: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(200))
    organizacao: Mapped[str | None] = mapped_column(String(200))
    uso_pretendido: Mapped[str] = mapped_column(String(40))
    email_verificado: Mapped[bool] = mapped_column(default=False)
    ativo: Mapped[bool] = mapped_column(default=True)
    # Nulo usa o limite padrão das configurações.
    limite_diario: Mapped[int | None] = mapped_column(Integer, default=None)
    falhas_login: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Sessao(Base):
    __tablename__ = "sessoes"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), index=True)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Verificacao(Base):
    """Token de confirmação de e-mail. Só o hash fica salvo."""

    __tablename__ = "verificacoes"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id"), index=True)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UsoDiario(Base):
    __tablename__ = "uso_diario"

    tenant_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    dia: Mapped[date] = mapped_column(Date, primary_key=True)
    consultas: Mapped[int] = mapped_column(Integer, default=0)
