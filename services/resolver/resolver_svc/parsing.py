"""Interpreta os campos em texto livre que os obituários costumam trazer."""

import re
from datetime import date

from morbidus_common.text import strip_accents

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


def parse_idade(texto: str | None) -> int | None:
    if not texto:
        return None
    m = re.search(r"(\d{1,3})\s*anos?", texto.lower())
    if not m:
        m = re.fullmatch(r"\s*(\d{1,3})\s*", texto)
    idade = int(m.group(1)) if m else None
    return idade if idade is not None and 0 <= idade <= 125 else None


def parse_data(texto: str | None, referencia: date) -> date | None:
    """Aceita "20/10/2026", "20/10/26", "20/10" e "20 de outubro de 2026".

    Sem ano, usa o da referência; se a data cair no futuro, é do ano anterior.
    """
    if not texto:
        return None
    t = strip_accents(texto.lower())
    m = re.search(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", t)
    if m:
        dia, mes, ano = int(m.group(1)), int(m.group(2)), m.group(3)
    else:
        m = re.search(r"(\d{1,2})\s+de\s+([a-z]+)(?:\s+de\s+(\d{4}))?", t)
        if not m or m.group(2) not in MESES:
            return None
        dia, mes, ano = int(m.group(1)), MESES[m.group(2)], m.group(3)
    try:
        if ano:
            ano_int = int(ano)
            return date(ano_int + 2000 if ano_int < 100 else ano_int, mes, dia)
        candidata = date(referencia.year, mes, dia)
        return candidata if candidata <= referencia else date(referencia.year - 1, mes, dia)
    except ValueError:
        return None
