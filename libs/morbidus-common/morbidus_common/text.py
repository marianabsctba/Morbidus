"""Normalização de nomes brasileiros, chave fonética e validação de CPF."""

import re
import unicodedata

from rapidfuzz import fuzz

_PARTICULAS = {"de", "da", "do", "das", "dos", "e", "d"}

# Regras aplicadas em ordem sobre cada token sem acento. "G" é marcador
# temporário para "gue/gui" não virar "je/ji" na regra seguinte.
_REGRAS_FONETICAS = [
    (r"lh", "l"),
    (r"nh", "n"),
    (r"ph", "f"),
    (r"[cs]h", "x"),
    (r"qu", "k"),
    (r"gu([ei])", r"G\1"),
    (r"g([ei])", r"j\1"),
    (r"G", "g"),
    (r"sc([ei])", r"s\1"),
    (r"c([ei])", r"s\1"),
    (r"[cq]", "k"),
    (r"y", "i"),
    (r"w", "v"),
    (r"z", "s"),
    (r"h", ""),
]


def strip_accents(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def _tokens(nome: str) -> list[str]:
    texto = strip_accents(nome.lower().replace("ç", "s"))
    texto = re.sub(r"[^a-z\s]", " ", texto)
    return [t for t in texto.split() if t not in _PARTICULAS]


def normalize_name(nome: str) -> str:
    return " ".join(_tokens(nome))


def _fonetica_token(token: str) -> str:
    for padrao, troca in _REGRAS_FONETICAS:
        token = re.sub(padrao, troca, token)
    if not token:
        return ""
    # Mantém a primeira letra e descarta as vogais seguintes, como no Soundex.
    corpo = re.sub(r"[aeiou]", "", token[1:])
    return re.sub(r"(.)\1+", r"\1", token[0] + corpo)


def phonetic_key(nome: str) -> str:
    """Chave para agrupar grafias parecidas (Souza/Sousa, Thiago/Tiago, Luiz/Luis)."""
    return " ".join(k for k in (_fonetica_token(t) for t in _tokens(nome)) if k)


def name_similarity(a: str, b: str) -> float:
    return fuzz.token_sort_ratio(normalize_name(a), normalize_name(b)) / 100


def only_digits(texto: str) -> str:
    return re.sub(r"\D", "", texto)


def cpf_with_check_digits(base9: str) -> str:
    digitos = [int(c) for c in base9]
    for peso_inicial in (10, 11):
        soma = sum(d * p for d, p in zip(digitos, range(peso_inicial, 1, -1)))
        resto = (soma * 10) % 11
        digitos.append(0 if resto == 10 else resto)
    return "".join(map(str, digitos))


def is_valid_cpf(cpf: str) -> bool:
    cpf = only_digits(cpf)
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False
    return cpf_with_check_digits(cpf[:9]) == cpf


def mask_cpf(cpf: str) -> str:
    cpf = only_digits(cpf)
    return f"***.{cpf[3:6]}.{cpf[6:9]}-**"
