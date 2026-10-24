from bs4 import BeautifulSoup

from crawler_svc.spiders.base import DATA_BR, ObituaryEntry, Page, PaginatedSpider, texto


class PaxUniaoTeresinaSpider(PaginatedSpider):
    """Obituário do Grupo Geraldo Oliveira (Pax União). A listagem cobre cerca de 3 semanas
    e inclui cidades do interior do Piauí atendidas pela rede."""

    source_id = "teresina-pax-uniao"
    cidade = "Teresina"
    uf = "PI"
    descricao = "Obituário do Grupo Geraldo Oliveira / Pax União"

    def page_url(self, n: int) -> str:
        base = "https://ggo-interno.com.br/obituario"
        return base if n == 1 else f"{base}?page={n}"

    def parse(self, page: Page) -> list[ObituaryEntry]:
        soup = BeautifulSoup(page.html, "html.parser")
        entries = []
        for card in soup.select("div.card .card-body"):
            nome = texto(card.select_one("strong.text-md"))
            if not nome:
                continue
            nascimento = falecimento = None
            for span in card.select(".header p span"):
                data = DATA_BR.search(span.get_text())
                if not data:
                    continue
                if span.select_one(".fa-star"):
                    nascimento = "/".join(data.groups())
                elif span.select_one(".fa-cross"):
                    falecimento = "/".join(data.groups())
            sepultamento = local = None
            for bloco in card.select("div.text-sm"):
                if "SEPULTAMENTO" in (texto(bloco.select_one("strong")) or "").upper():
                    corpo = bloco.get_text("\n", strip=True)
                    data = DATA_BR.search(corpo)
                    sepultamento = "/".join(data.groups()) if data else None
                    for linha in corpo.split("\n"):
                        if linha.lower().startswith("cemitério:"):
                            local = linha.split(":", 1)[1].strip() or None
            entries.append(
                ObituaryEntry(
                    nome=nome,
                    data_nascimento=nascimento,
                    data_falecimento=falecimento,
                    data_sepultamento=sepultamento,
                    local=local,
                )
            )
        return entries
