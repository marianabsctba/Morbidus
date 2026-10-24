"""Segundo fator por TOTP (RFC 6238), compatível com Google/Microsoft Authenticator e afins."""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken

PASSO_SEGUNDOS = 30
DIGITOS = 6
_ALFABETO_RECUPERACAO = "abcdefghjkmnpqrstuvwxyz23456789"  # sem 0/o, 1/l/i


def novo_segredo() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _hotp(segredo_b32: str, contador: int) -> str:
    chave = base64.b32decode(segredo_b32 + "=" * (-len(segredo_b32) % 8))
    mac = hmac.new(chave, struct.pack(">Q", contador), hashlib.sha1).digest()
    deslocamento = mac[-1] & 0x0F
    valor = struct.unpack(">I", mac[deslocamento : deslocamento + 4])[0] & 0x7FFFFFFF
    return str(valor % 10**DIGITOS).zfill(DIGITOS)


def passo_atual(agora: float | None = None) -> int:
    return int((time.time() if agora is None else agora) // PASSO_SEGUNDOS)


def confere_totp(segredo_b32: str, codigo: str, ultimo_passo: int | None, agora: float | None = None) -> int | None:
    """Devolve o passo aceito, ou None. Tolera 30 s de relógio adiantado ou atrasado
    e recusa reutilizar um código (ou um anterior) já aceito."""
    codigo = codigo.replace(" ", "").strip()
    if len(codigo) != DIGITOS or not codigo.isdigit():
        return None
    atual = passo_atual(agora)
    for passo in (atual - 1, atual, atual + 1):
        if ultimo_passo is not None and passo <= ultimo_passo:
            continue
        if hmac.compare_digest(_hotp(segredo_b32, passo), codigo):
            return passo
    return None


def uri_otpauth(segredo_b32: str, conta: str, emissor: str = "MORBiDus") -> str:
    rotulo = quote(f"{emissor}:{conta}")
    return f"otpauth://totp/{rotulo}?secret={segredo_b32}&issuer={quote(emissor)}&algorithm=SHA1&digits={DIGITOS}&period={PASSO_SEGUNDOS}"


def codigos_recuperacao(quantidade: int = 8) -> list[str]:
    def um() -> str:
        bruto = "".join(secrets.choice(_ALFABETO_RECUPERACAO) for _ in range(10))
        return f"{bruto[:5]}-{bruto[5:]}"

    return [um() for _ in range(quantidade)]


def normaliza_recuperacao(codigo: str) -> str:
    return codigo.strip().lower().replace(" ", "").replace("-", "")


class Cofre:
    """Cifra o segredo TOTP no banco: vazar só o banco não basta para gerar códigos."""

    def __init__(self, segredo_servidor: str) -> None:
        chave = base64.urlsafe_b64encode(hashlib.sha256(f"morbidus-mfa:{segredo_servidor}".encode()).digest())
        self._fernet = Fernet(chave)

    def cifra(self, segredo_b32: str) -> str:
        return self._fernet.encrypt(segredo_b32.encode()).decode()

    def decifra(self, cifrado: str) -> str | None:
        try:
            return self._fernet.decrypt(cifrado.encode()).decode()
        except InvalidToken:
            return None
