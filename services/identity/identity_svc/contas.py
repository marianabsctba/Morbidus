"""Cadastro, login por sessão (cookie), autoatendimento de API keys e administração de usuários.

Toda conta nasce bloqueada. Com SMTP, libera ao confirmar o e-mail; sem SMTP, quando
uma administradora aprova. O campo `email_verificado` guarda essa liberação.
"""

import re
from datetime import date, datetime, timedelta, timezone
from enum import Enum

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Response
from morbidus_common.db import utcnow
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from identity_svc.config import IdentitySettings
from identity_svc.correio import envia_confirmacao
from identity_svc.keys import generate_key
from identity_svc.models import Administrador, ApiKey, Sessao, Tenant, UsoDiario, Usuario, Verificacao
from identity_svc.seguranca import SENHA_FALSA, confere_senha, hash_senha, hash_token, novo_token

COOKIE = "mbd_sessao"
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
_MAX_FALHAS = 5
_BLOQUEIO = timedelta(minutes=15)


class UsoPretendido(str, Enum):
    ONBOARDING = "onboarding"
    CREDITO = "concessao_credito"
    FRAUDE = "prevencao_fraude"
    BENEFICIO = "pagamento_beneficio"
    SEGURO = "sinistro_seguro"
    PESQUISA = "pesquisa"


class CadastroIn(BaseModel):
    nome: str = Field(min_length=3, max_length=200)
    email: str = Field(max_length=254)
    senha: str = Field(min_length=10, max_length=200)
    organizacao: str | None = Field(default=None, max_length=200)
    uso_pretendido: UsoPretendido
    aceite_termos: bool

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL.match(v):
            raise ValueError("e-mail inválido")
        return v

    @field_validator("aceite_termos")
    @classmethod
    def _aceite(cls, v: bool) -> bool:
        if not v:
            raise ValueError("é preciso aceitar os termos de uso")
        return v


class LoginIn(BaseModel):
    email: str
    senha: str


class TokenIn(BaseModel):
    token: str


class ContaOut(BaseModel):
    nome: str
    email: str
    organizacao: str | None
    uso_pretendido: str
    limite_diario: int
    consultas_hoje: int
    criado_em: datetime
    admin: bool


class UsuarioAdmin(BaseModel):
    id: str
    tenant_id: str
    nome: str
    email: str
    organizacao: str | None
    uso_pretendido: str
    liberado: bool
    ativo: bool
    admin: bool
    limite_diario: int
    consultas_hoje: int
    criado_em: datetime


class UsuarioAdminIn(BaseModel):
    liberado: bool | None = None
    ativo: bool | None = None
    admin: bool | None = None
    # 0 libera consultas ilimitadas; nulo volta ao padrão.
    limite_diario: int | None = Field(default=None, ge=0)


class ApiKeyIn(BaseModel):
    nome: str = Field(min_length=2, max_length=100)


class ApiKeyOut(BaseModel):
    id: str
    nome: str
    prefixo: str
    criado_em: datetime
    revogada_em: datetime | None


class ApiKeyNova(ApiKeyOut):
    chave: str = Field(description="Exibida uma única vez.")


def hoje() -> date:
    return datetime.now(timezone.utc).date()


def limite_do_tenant(db: Session, settings: IdentitySettings, tenant_id: str) -> int:
    usuario = db.scalar(select(Usuario).where(Usuario.tenant_id == tenant_id))
    if usuario and usuario.limite_diario is not None:
        return usuario.limite_diario
    return settings.limite_diario_padrao


def consultas_hoje(db: Session, tenant_id: str) -> int:
    uso = db.get(UsoDiario, (tenant_id, hoje()))
    return uso.consultas if uso else 0


def usuario_da_sessao(db: Session, token: str | None) -> Usuario | None:
    if not token:
        return None
    sessao = db.get(Sessao, hash_token(token))
    if sessao is None or _aware(sessao.expira_em) < utcnow():
        return None
    usuario = db.get(Usuario, sessao.usuario_id)
    if usuario is None or not usuario.ativo or not usuario.email_verificado:
        return None
    return usuario


def eh_admin(db: Session, usuario_id: str) -> bool:
    return db.get(Administrador, usuario_id) is not None


def _aware(dt: datetime) -> datetime:
    # SQLite devolve datas sem fuso; o Postgres devolve com fuso.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def build_router(settings: IdentitySettings, get_db) -> APIRouter:
    router = APIRouter(tags=["contas"])
    email_obrigatorio = bool(settings.smtp_host)

    def usuario_logado(mbd_sessao: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> Usuario:
        usuario = usuario_da_sessao(db, mbd_sessao)
        if usuario is None:
            raise HTTPException(status_code=401, detail="faça login para continuar")
        return usuario

    def admin_logado(usuario: Usuario = Depends(usuario_logado), db: Session = Depends(get_db)) -> Usuario:
        if not eh_admin(db, usuario.id):
            raise HTTPException(status_code=403, detail="acesso restrito à administração")
        return usuario

    def _para_admin(db: Session, u: Usuario) -> UsuarioAdmin:
        return UsuarioAdmin(
            id=u.id,
            tenant_id=u.tenant_id,
            nome=u.nome,
            email=u.email,
            organizacao=u.organizacao,
            uso_pretendido=u.uso_pretendido,
            liberado=u.email_verificado,
            ativo=u.ativo,
            admin=eh_admin(db, u.id),
            limite_diario=limite_do_tenant(db, settings, u.tenant_id),
            consultas_hoje=consultas_hoje(db, u.tenant_id),
            criado_em=u.criado_em,
        )

    @router.post("/v1/contas", status_code=201)
    def cadastrar(body: CadastroIn, tarefas: BackgroundTasks, db: Session = Depends(get_db)):
        if db.scalar(select(Usuario).where(Usuario.email == body.email)):
            raise HTTPException(status_code=409, detail="já existe uma conta com este e-mail")
        tenant = Tenant(nome=body.organizacao or body.nome)
        db.add(tenant)
        db.flush()
        usuario = Usuario(
            tenant_id=tenant.id,
            nome=body.nome.strip(),
            email=body.email,
            senha_hash=hash_senha(body.senha),
            organizacao=(body.organizacao or "").strip() or None,
            uso_pretendido=body.uso_pretendido.value,
            email_verificado=False,
        )
        db.add(usuario)
        db.flush()
        if email_obrigatorio:
            token, digest = novo_token()
            db.add(Verificacao(token_hash=digest, usuario_id=usuario.id, expira_em=utcnow() + timedelta(hours=24)))
            tarefas.add_task(envia_confirmacao, settings, usuario.email, usuario.nome, token)
        db.commit()
        return {"verificacao_necessaria": email_obrigatorio, "aprovacao_necessaria": not email_obrigatorio}

    @router.post("/v1/contas/verificar")
    def verificar(body: TokenIn, db: Session = Depends(get_db)):
        verificacao = db.get(Verificacao, hash_token(body.token))
        if verificacao is None or _aware(verificacao.expira_em) < utcnow():
            raise HTTPException(status_code=400, detail="link inválido ou expirado")
        usuario = db.get(Usuario, verificacao.usuario_id)
        usuario.email_verificado = True
        db.delete(verificacao)
        db.commit()
        return {"ok": True}

    @router.post("/v1/sessao")
    def entrar(body: LoginIn, response: Response, db: Session = Depends(get_db)):
        usuario = db.scalar(select(Usuario).where(Usuario.email == body.email.strip().lower()))
        if usuario and usuario.bloqueado_ate and _aware(usuario.bloqueado_ate) > utcnow():
            raise HTTPException(status_code=429, detail="muitas tentativas; tente de novo em alguns minutos")
        if usuario is None:
            confere_senha(body.senha, SENHA_FALSA)
            raise HTTPException(status_code=401, detail="e-mail ou senha incorretos")
        if not confere_senha(body.senha, usuario.senha_hash):
            usuario.falhas_login += 1
            if usuario.falhas_login >= _MAX_FALHAS:
                usuario.bloqueado_ate = utcnow() + _BLOQUEIO
                usuario.falhas_login = 0
            db.commit()
            raise HTTPException(status_code=401, detail="e-mail ou senha incorretos")
        if not usuario.ativo:
            raise HTTPException(status_code=403, detail="conta desativada")
        if not usuario.email_verificado:
            if db.scalar(select(Verificacao).where(Verificacao.usuario_id == usuario.id)):
                raise HTTPException(status_code=403, detail="confirme seu e-mail antes de entrar")
            raise HTTPException(status_code=403, detail="sua conta aguarda aprovação da administração")
        usuario.falhas_login = 0
        usuario.bloqueado_ate = None
        agora = utcnow()
        for velha in db.scalars(select(Sessao).where(Sessao.usuario_id == usuario.id)):
            if _aware(velha.expira_em) < agora:
                db.delete(velha)
        token, digest = novo_token()
        db.add(Sessao(token_hash=digest, usuario_id=usuario.id, expira_em=agora + timedelta(hours=settings.sessao_horas)))
        db.commit()
        response.set_cookie(
            COOKIE,
            token,
            max_age=settings.sessao_horas * 3600,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="strict",
            path="/",
        )
        return {"nome": usuario.nome, "email": usuario.email}

    @router.delete("/v1/sessao", status_code=204)
    def sair(response: Response, mbd_sessao: str | None = Cookie(default=None), db: Session = Depends(get_db)):
        if mbd_sessao:
            sessao = db.get(Sessao, hash_token(mbd_sessao))
            if sessao:
                db.delete(sessao)
                db.commit()
        response.delete_cookie(COOKIE, path="/", secure=settings.cookie_secure, httponly=True, samesite="strict")

    @router.get("/v1/conta", response_model=ContaOut)
    def minha_conta(usuario: Usuario = Depends(usuario_logado), db: Session = Depends(get_db)):
        return ContaOut(
            nome=usuario.nome,
            email=usuario.email,
            organizacao=usuario.organizacao,
            uso_pretendido=usuario.uso_pretendido,
            limite_diario=limite_do_tenant(db, settings, usuario.tenant_id),
            consultas_hoje=consultas_hoje(db, usuario.tenant_id),
            criado_em=usuario.criado_em,
            admin=eh_admin(db, usuario.id),
        )

    @router.get("/v1/conta/admin/usuarios", response_model=list[UsuarioAdmin])
    def listar_usuarios(_: Usuario = Depends(admin_logado), db: Session = Depends(get_db)):
        return [_para_admin(db, u) for u in db.scalars(select(Usuario).order_by(Usuario.criado_em.desc()))]

    @router.patch("/v1/conta/admin/usuarios/{usuario_id}", response_model=UsuarioAdmin)
    def alterar_usuario(
        usuario_id: str,
        body: UsuarioAdminIn,
        eu: Usuario = Depends(admin_logado),
        db: Session = Depends(get_db),
    ):
        alvo = db.get(Usuario, usuario_id)
        if alvo is None:
            raise HTTPException(status_code=404, detail="usuário não encontrado")
        mudancas = body.model_dump(exclude_unset=True)
        if alvo.id == eu.id and (mudancas.get("admin") is False or mudancas.get("ativo") is False):
            raise HTTPException(status_code=400, detail="você não pode tirar seu próprio acesso")
        if "liberado" in mudancas:
            alvo.email_verificado = bool(mudancas["liberado"])
        if "ativo" in mudancas:
            alvo.ativo = bool(mudancas["ativo"])
        if "limite_diario" in mudancas:
            alvo.limite_diario = mudancas["limite_diario"]
        if "admin" in mudancas:
            atual = db.get(Administrador, alvo.id)
            if mudancas["admin"] and atual is None:
                db.add(Administrador(usuario_id=alvo.id))
            elif not mudancas["admin"] and atual is not None:
                db.delete(atual)
        if mudancas.get("ativo") is False:
            # Bloquear derruba as sessões abertas na hora.
            for sessao in db.scalars(select(Sessao).where(Sessao.usuario_id == alvo.id)):
                db.delete(sessao)
        db.commit()
        return _para_admin(db, alvo)

    if not settings.api_keys_habilitadas:
        return router

    @router.get("/v1/conta/api-keys", response_model=list[ApiKeyOut])
    def minhas_chaves(usuario: Usuario = Depends(usuario_logado), db: Session = Depends(get_db)):
        return db.scalars(
            select(ApiKey).where(ApiKey.tenant_id == usuario.tenant_id).order_by(ApiKey.criado_em.desc())
        ).all()

    @router.post("/v1/conta/api-keys", response_model=ApiKeyNova, status_code=201)
    def gerar_chave(body: ApiKeyIn, usuario: Usuario = Depends(usuario_logado), db: Session = Depends(get_db)):
        ativas = db.scalar(
            select(func.count())
            .select_from(ApiKey)
            .where(ApiKey.tenant_id == usuario.tenant_id, ApiKey.revogada_em.is_(None))
        )
        if ativas >= settings.max_api_keys_por_conta:
            raise HTTPException(status_code=409, detail=f"limite de {settings.max_api_keys_por_conta} chaves ativas")
        chave, prefixo, digest = generate_key(settings.api_key_pepper)
        key = ApiKey(tenant_id=usuario.tenant_id, nome=body.nome.strip(), prefixo=prefixo, hash=digest)
        db.add(key)
        db.commit()
        return ApiKeyNova(
            id=key.id, nome=key.nome, prefixo=prefixo, criado_em=key.criado_em, revogada_em=None, chave=chave
        )

    @router.delete("/v1/conta/api-keys/{key_id}", status_code=204)
    def revogar_chave(key_id: str, usuario: Usuario = Depends(usuario_logado), db: Session = Depends(get_db)):
        key = db.get(ApiKey, key_id)
        if key is None or key.tenant_id != usuario.tenant_id:
            raise HTTPException(status_code=404, detail="chave não encontrada")
        key.revogada_em = key.revogada_em or utcnow()
        db.commit()

    return router
