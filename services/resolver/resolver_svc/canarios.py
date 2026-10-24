"""Identidades-canário: pessoas falecidas fictícias plantadas na base.

O nome de um canário só existe dentro do MORBiDus. Se alguém consulta esse nome, ou se ele
aparece numa fraude ou num vazamento, a base foi extraída de algum jeito.
"""

import random
from datetime import date, timedelta

from morbidus_common.events import DeathRecordNormalized
from morbidus_common.search import DeathIndex
from morbidus_common.text import name_similarity, normalize_name, phonetic_key
from sqlalchemy import select
from sqlalchemy.orm import Session

from resolver_svc.models import DeathRecord
from resolver_svc.resolver import to_event

# Prenomes e sobrenomes raros: a combinação de três deles praticamente não existe.
_PRENOMES = [
    "Gumercindo", "Belarmina", "Eustórgio", "Ludovina", "Teodolinda", "Anacleto", "Florisbela", "Hermengarda",
    "Clodomiro", "Zulmira", "Policarpo", "Etelvina", "Diomedes", "Leocádia", "Saturnino", "Doralice",
    "Epaminondas", "Filomena", "Laurindo", "Gertrudes", "Olegário", "Ermelinda", "Nicanor", "Escolástica",
    "Ataliba", "Brasilina", "Cândido", "Deolinda", "Juvenal", "Rosalva", "Teotônio", "Umbelina",
]
_MEIOS = [
    "Belarmino", "Quaresma", "Valadares", "Bittencourt", "Cavalcanti", "Sobreira", "Magalhães", "Albuquerque",
    "Vasconcelos", "Sampaio", "Bezerril", "Arruda", "Peçanha", "Tavares", "Brandão", "Figueiró",
]
_SOBRENOMES = [
    "Quintanilha", "Anunciação", "Esteves", "Mascarenhas", "Prudente", "Assumpção", "Trindade", "Goulart",
    "Montenegro", "Paranhos", "Saldanha", "Cerqueira", "Lacerda", "Bragança", "Moniz", "Falcão",
]
# Onde há fonte ativa: um canário precisa parecer um registro comum.
_LOCAIS = [
    ("Curitiba", "PR"), ("Porto Alegre", "RS"), ("Salvador", "BA"), ("Brasília", "DF"), ("Natal", "RN"),
    ("Palmas", "TO"), ("Teresina", "PI"), ("Boa Vista", "RR"), ("Cuiabá", "MT"), ("Campo Grande", "MS"),
]


def _nome_livre(db: Session, index: DeathIndex, nome: str) -> bool:
    """Recusa nomes que lembrem qualquer pessoa da base, real ou canário."""
    chave = phonetic_key(nome)
    if db.scalar(select(DeathRecord.id).where(DeathRecord.chave_fonetica == chave)):
        return False
    return all(name_similarity(nome, doc["nome"]) < 0.6 for doc in index.search(nome, limit=5))


def plantar(db: Session, index: DeathIndex, quantidade: int, hoje: date | None = None) -> list[DeathRecordNormalized]:
    hoje = hoje or date.today()
    sorteio = random.SystemRandom()
    criados: list[DeathRecordNormalized] = []
    tentativas = 0
    while len(criados) < quantidade and tentativas < quantidade * 50:
        tentativas += 1
        nome = f"{sorteio.choice(_PRENOMES)} {sorteio.choice(_MEIOS)} {sorteio.choice(_SOBRENOMES)}"
        if not _nome_livre(db, index, nome):
            continue
        nascimento = date(sorteio.randint(1932, 1962), sorteio.randint(1, 12), sorteio.randint(1, 28))
        falecimento = hoje - timedelta(days=sorteio.randint(20, 540))
        cidade, uf = sorteio.choice(_LOCAIS)
        idade = falecimento.year - nascimento.year - ((falecimento.month, falecimento.day) < (nascimento.month, nascimento.day))
        registro = DeathRecord(
            nome=nome.upper(),
            nome_normalizado=normalize_name(nome),
            chave_fonetica=phonetic_key(nome),
            idade=idade,
            data_nascimento=nascimento,
            data_falecimento=falecimento,
            ano_nascimento_estimado=nascimento.year,
            cidade=cidade,
            uf=uf,
            fontes=["canario"],
            canario=True,
        )
        db.add(registro)
        db.flush()
        evento = to_event(registro)
        index.upsert(evento)
        criados.append(evento)
    db.commit()
    return criados
