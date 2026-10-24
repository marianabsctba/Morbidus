"""Senhas com scrypt e tokens opacos (sessão, confirmação de e-mail)."""

import base64
import hashlib
import hmac
import secrets

_N, _R, _P, _TAM = 2**14, 8, 1, 32


def hash_senha(senha: str) -> str:
    sal = secrets.token_bytes(16)
    dk = hashlib.scrypt(senha.encode(), salt=sal, n=_N, r=_R, p=_P, dklen=_TAM)
    return "scrypt${}${}${}${}${}".format(
        _N, _R, _P, base64.b64encode(sal).decode(), base64.b64encode(dk).decode()
    )


def confere_senha(senha: str, armazenado: str) -> bool:
    try:
        _, n, r, p, sal, dk = armazenado.split("$")
        calculado = hashlib.scrypt(
            senha.encode(), salt=base64.b64decode(sal), n=int(n), r=int(r), p=int(p), dklen=len(base64.b64decode(dk))
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calculado, base64.b64decode(dk))


# Hash de uma senha qualquer, para gastar o mesmo tempo quando o e-mail não existe.
SENHA_FALSA = hash_senha(secrets.token_urlsafe(16))


def novo_token() -> tuple[str, str]:
    """Retorna (token para o cliente, hash para o banco)."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
