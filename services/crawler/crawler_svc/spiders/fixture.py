from pathlib import Path

from bs4 import BeautifulSoup

from crawler_svc.fetcher import PoliteFetcher
from crawler_svc.spiders.base import ObituaryEntry, Page, Spider

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "obituario_exemplo.html"


class FixtureSpider(Spider):
    """Lê uma página local com obituários fictícios. Serve de modelo para spiders reais."""

    source_id = "fixture"
    cidade = "Curitiba"
    uf = "PR"

    async def fetch_pages(self, fetcher: PoliteFetcher) -> list[Page]:
        return [Page(url=f"fixture://{FIXTURE.name}", html=FIXTURE.read_text(encoding="utf-8"))]

    def parse(self, page: Page) -> list[ObituaryEntry]:
        soup = BeautifulSoup(page.html, "html.parser")

        def texto(item, classe):
            tag = item.select_one(f".{classe}")
            return tag.get_text(strip=True) if tag else None

        return [
            ObituaryEntry(
                nome=texto(item, "nome"),
                idade=texto(item, "idade"),
                data_falecimento=texto(item, "falecimento"),
                data_sepultamento=texto(item, "sepultamento"),
                local=texto(item, "local"),
            )
            for item in soup.select("li.obito")
            if texto(item, "nome")
        ]
