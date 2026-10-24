"""Score de um candidato vindo de obituário. Sem CPF no obituário, é sempre probabilístico."""

from datetime import date

from morbidus_common.text import name_similarity, phonetic_key, strip_accents


def _cidade(texto: str) -> str:
    return strip_accents(texto).strip().lower()


def score_candidate(
    candidato: dict,
    nome: str,
    uf: str | None,
    cidade: str | None,
    data_nascimento: date | None,
) -> tuple[float, list[str]]:
    similaridade = name_similarity(nome, candidato["nome"])
    score = 0.6 * similaridade
    motivos = [f"nome {similaridade:.0%} similar"]

    if candidato.get("chave_fonetica") == phonetic_key(nome):
        score += 0.1
        motivos.append("mesma chave fonética")
    if uf and candidato.get("uf") == uf.upper():
        score += 0.1
        motivos.append("mesma UF")
    if cidade and _cidade(candidato.get("cidade", "")) == _cidade(cidade):
        score += 0.1
        motivos.append("mesma cidade")

    nascimento = candidato.get("data_nascimento")
    ano_estimado = candidato.get("ano_nascimento_estimado")
    if data_nascimento and nascimento:
        if nascimento == data_nascimento.isoformat():
            score += 0.2
            motivos.append("data de nascimento idêntica")
        else:
            score -= 0.4
            motivos.append("data de nascimento diferente")
    elif data_nascimento and ano_estimado:
        # Idade no obituário pode não ter feito aniversário ainda: tolera 1 ano.
        if abs(ano_estimado - data_nascimento.year) <= 1:
            score += 0.1
            motivos.append("idade compatível com a data de nascimento")
        else:
            score -= 0.3
            motivos.append("idade incompatível com a data de nascimento")

    return max(0.0, min(1.0, round(score, 3))), motivos
