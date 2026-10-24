"""Canal do titular (LGPD, art. 18): formulário público para falar com o encarregado (DPO)."""

import logging
import secrets
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from morbidus_common.correio import enviar, mensagem
from morbidus_common.db import utcnow
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from identity_svc.config import IdentitySettings
from identity_svc.contas import _EMAIL, ip_da_requisicao
from identity_svc.models import Administrador, SolicitacaoTitular, Usuario

log = logging.getLogger(__name__)

PRAZO_DIAS = 15


class TipoSolicitacao(str, Enum):
    ACESSO = "acesso"
    CORRECAO = "correcao"
    ELIMINACAO = "eliminacao"
    REMOCAO_OBITO = "remocao_registro_obito"
    INFORMACAO = "informacao"
    OUTRO = "outro"


ROTULOS = {
    "acesso": "Acesso aos meus dados",
    "correcao": "Correção de dados",
    "eliminacao": "Eliminação dos meus dados",
    "remocao_registro_obito": "Correção ou remoção de registro de óbito de familiar",
    "informacao": "Informação sobre tratamento ou compartilhamento",
    "outro": "Outro assunto",
}


class SolicitacaoIn(BaseModel):
    nome: str = Field(min_length=3, max_length=200)
    email: str = Field(max_length=254)
    tipo: TipoSolicitacao
    mensagem: str = Field(min_length=10, max_length=4000)
    # Campo-armadilha: invisível no formulário. Gente não preenche; robô costuma preencher.
    site: str | None = Field(default=None, max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL.match(v):
            raise ValueError("e-mail inválido")
        return v


class SolicitacaoOut(BaseModel):
    id: str
    protocolo: str
    nome: str
    email: str
    tipo: str
    rotulo: str
    mensagem: str
    status: str
    criado_em: datetime
    atendido_em: datetime | None
    observacao: str | None


class SolicitacaoAdminIn(BaseModel):
    status: str = Field(pattern="^(aberta|atendida)$")
    observacao: str | None = Field(default=None, max_length=2000)


def _protocolo() -> str:
    return f"MBD-{utcnow():%Y%m%d}-{secrets.token_hex(3).upper()}"


def _out(s: SolicitacaoTitular) -> SolicitacaoOut:
    return SolicitacaoOut(
        id=s.id,
        protocolo=s.protocolo,
        nome=s.nome,
        email=s.email,
        tipo=s.tipo,
        rotulo=ROTULOS.get(s.tipo, s.tipo),
        mensagem=s.mensagem,
        status=s.status,
        criado_em=s.criado_em,
        atendido_em=s.atendido_em,
        observacao=s.observacao,
    )


def _avisar(settings: IdentitySettings, solicitacao: SolicitacaoOut, admins: list[str]) -> None:
    if not settings.smtp_host:
        return
    painel = f"{settings.public_url.rstrip('/')}/admin"
    try:
        enviar(
            settings,
            mensagem(
                settings,
                solicitacao.email,
                f"[MORBiDus] Recebemos sua solicitação {solicitacao.protocolo}",
                f"Olá, {solicitacao.nome}.\n\n"
                f"Recebemos sua solicitação ({solicitacao.rotulo}) com o protocolo {solicitacao.protocolo}.\n"
                f"Vamos responder neste e-mail em até {PRAZO_DIAS} dias.\n\n"
                "Se você não fez esta solicitação, ignore esta mensagem.\n\n"
                "MORBiDus · Encarregado de proteção de dados",
            ),
        )
        if admins:
            enviar(
                settings,
                mensagem(
                    settings,
                    admins,
                    f"[MORBiDus] Nova solicitação de titular {solicitacao.protocolo}",
                    f"Tipo: {solicitacao.rotulo}\nDe: {solicitacao.nome} <{solicitacao.email}>\n\n"
                    f"{solicitacao.mensagem}\n\nPrazo de resposta: {PRAZO_DIAS} dias.\nAcompanhe em: {painel}\n",
                ),
            )
    except Exception:
        log.exception("falha ao enviar e-mails da solicitação %s", solicitacao.protocolo)


def build_router(settings: IdentitySettings, get_db, admin_logado) -> APIRouter:
    router = APIRouter(tags=["titulares"])

    @router.post("/v1/privacidade/solicitacoes", status_code=201)
    def solicitar(body: SolicitacaoIn, request: Request, tarefas: BackgroundTasks, db: Session = Depends(get_db)):
        if body.site:
            # Robô caiu na armadilha: responde como sucesso para não ensinar o truque.
            return {"protocolo": _protocolo(), "prazo_dias": PRAZO_DIAS}
        registro = SolicitacaoTitular(
            protocolo=_protocolo(),
            nome=body.nome.strip(),
            email=body.email,
            tipo=body.tipo.value,
            mensagem=body.mensagem.strip(),
            ip=ip_da_requisicao(request),
        )
        db.add(registro)
        db.commit()
        admins = [
            u.email
            for u in (db.get(Usuario, a) for a in db.scalars(select(Administrador.usuario_id)))
            if u is not None and u.ativo
        ]
        tarefas.add_task(_avisar, settings, _out(registro), admins)
        return {"protocolo": registro.protocolo, "prazo_dias": PRAZO_DIAS}

    @router.get("/v1/conta/admin/solicitacoes", response_model=list[SolicitacaoOut])
    def listar(_: Usuario = Depends(admin_logado), db: Session = Depends(get_db)):
        consulta = select(SolicitacaoTitular).order_by(SolicitacaoTitular.criado_em.desc())
        return [_out(s) for s in db.scalars(consulta)]

    @router.patch("/v1/conta/admin/solicitacoes/{solicitacao_id}", response_model=SolicitacaoOut)
    def atualizar(
        solicitacao_id: str, body: SolicitacaoAdminIn, _: Usuario = Depends(admin_logado), db: Session = Depends(get_db)
    ):
        registro = db.get(SolicitacaoTitular, solicitacao_id)
        if registro is None:
            raise HTTPException(status_code=404, detail="solicitação não encontrada")
        registro.status = body.status
        registro.atendido_em = utcnow() if body.status == "atendida" else None
        if body.observacao is not None:
            registro.observacao = body.observacao
        db.commit()
        return _out(registro)

    return router
