import re

from bs4 import BeautifulSoup

from crawler_svc.spiders.base import DATA_BR, ObituaryEntry, Page, PaginatedSpider, texto

LISTAGEM = "https://grupopaxpalmas.com.br/obituario"


class PaxPalmasSpider(PaginatedSpider):
    """Listagem em ordem crescente: o mais recente fica na última página.

    O robots.txt bloqueia /obito/ (detalhe), então só a listagem é lida.
    """

    source_id = "palmas-pax"
    cidade = "Palmas"
    uf = "TO"
    descricao = "Avisos de falecimento do Grupo Pax Palmas (só listagem)"

    def page_url(self, n: int) -> str:
        return f"{LISTAGEM}?page={n}"

    async def iter_pages(self, fetcher, backfill=False, max_pages=None):
        primeira = Page(url=self.page_url(1), html=await fetcher.get(self.page_url(1)))
        ultima = max((int(n) for n in re.findall(r"obituario\?page=(\d+)", primeira.html)), default=1)
        if backfill:
            yield primeira
            fim = min(ultima, max_pages or ultima)
            paginas = range(2, fim + 1)
        else:
            paginas = range(max(1, ultima - self.incremental_pages + 1), ultima + 1)
        for n in paginas:
            page = Page(url=self.page_url(n), html=await fetcher.get(self.page_url(n)))
            yield page

    def parse(self, page: Page) -> list[ObituaryEntry]:
        soup = BeautifulSoup(page.html, "html.parser")
        entries = []
        for bloco in soup.select("span.thumb-info-inner"):
            data_tag = bloco.find("em")
            data = DATA_BR.search(texto(data_tag) or "")
            if data_tag:
                data_tag.extract()
            nome = texto(bloco)
            if nome:
                entries.append(ObituaryEntry(nome=nome, data_falecimento="/".join(data.groups()) if data else None))
        return entries
