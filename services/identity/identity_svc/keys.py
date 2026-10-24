"""API keys no formato `mbd_<prefixo>_<segredo>`. Só o hash fica no banco."""

import hashlib
import hmac
import secrets


def hash_key(key: str, pepper: str) -> str:
    return hmac.new(pepper.encode(), key.encode(), hashlib.sha256).hexdigest()


def generate_key(pepper: str) -> tuple[str, str, str]:
    """Retorna (chave completa, prefixo, hash)."""
    prefixo = secrets.token_hex(4)
    chave = f"mbd_{prefixo}_{secrets.token_urlsafe(24)}"
    return chave, prefixo, hash_key(chave, pepper)


def parse_prefix(key: str) -> str | None:
    partes = key.split("_", 2)
    if len(partes) != 3 or partes[0] != "mbd":
        return None
    return partes[1]
