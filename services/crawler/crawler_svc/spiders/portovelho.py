import re

from bs4 import BeautifulSoup

from crawler_svc.spiders.base import ObituaryEntry, Page, PaginatedSpider

_DATA_URL = re.compile(r"/obituarionews/(\d{4})/(\d{2})/(\d{2})/")
_PREFIXO = re.compile(r"^\s*nota\s+de\s+pesar\s*[:\-]?\s*", re.I)


class NewsRondoniaSpider(PaginatedSpider):
    """Lê só a listagem: o título traz o nome e a URL traz a data de publicação.

    As notas completas têm texto livre sobre a família e não são abertas.
    """

    source_id = "portovelho-news-rondonia"
    cidade = "Porto Velho"
    uf = "RO"
    descricao = "Notas de pesar publicadas pelo News Rondônia a pedido das funerárias"

    def page_url(self, n: int) -> str:
        base = "https://newsrondonia.com.br/obituario/"
        return base if n == 1 else f"{base}page/{n}/"

    def parse(self, page: Page) -> list[ObituaryEntry]:
        soup = BeautifulSoup(page.html, "html.parser")
        entries = []
        for card in soup.select("article.summary-horizontal-post-card-obituario"):
            link = card.select_one('a[href*="/obituarionews/"]')
            img = card.select_one("img[alt]")
            titulo = img["alt"] if img else (link.get_text(" ", strip=True) if link else "")
            data = _DATA_URL.search(link["href"]) if link else None
            nome = _PREFIXO.sub("", titulo).strip()
            if nome:
                entries.append(
                    ObituaryEntry(
                        nome=nome,
                        # Data de publicação da nota, normalmente o dia do velório.
                        data_sepultamento=f"{data.group(3)}/{data.group(2)}/{data.group(1)}" if data else None,
                        url=link["href"] if link else None,
                    )
                )
        return entries
