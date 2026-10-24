from pathlib import Path

from bs4 import BeautifulSoup

from crawler_svc.spiders.base import ObituaryEntry, Page, Spider, texto

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "obituario_exemplo.html"


class FixtureSpider(Spider):
    """Lê uma página local com obituários fictícios. Serve de modelo para spiders reais."""

    source_id = "fixture"
    cidade = "Curitiba"
    uf = "PR"
    descricao = "Página local com pessoas fictícias, para desenvolvimento"

    async def iter_pages(self, fetcher, backfill=False, max_pages=None):
        yield Page(url=f"fixture://{FIXTURE.name}", html=FIXTURE.read_text(encoding="utf-8"))

    def parse(self, page: Page) -> list[ObituaryEntry]:
        soup = BeautifulSoup(page.html, "html.parser")
        return [
            ObituaryEntry(
                nome=texto(item.select_one(".nome")),
                idade=texto(item.select_one(".idade")),
                data_falecimento=texto(item.select_one(".falecimento")),
                data_sepultamento=texto(item.select_one(".sepultamento")),
                local=texto(item.select_one(".local")),
            )
            for item in soup.select("li.obito")
            if item.select_one(".nome")
        ]
