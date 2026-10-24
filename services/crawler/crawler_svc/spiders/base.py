from dataclasses import dataclass

from crawler_svc.fetcher import PoliteFetcher


@dataclass
class Page:
    url: str
    html: str


@dataclass
class ObituaryEntry:
    """Só dados do falecido. Parentes citados no obituário nunca são extraídos (LGPD)."""

    nome: str
    idade: str | None = None
    data_falecimento: str | None = None
    data_sepultamento: str | None = None
    local: str | None = None


class Spider:
    source_id: str
    cidade: str
    uf: str
    start_urls: list[str] = []

    async def fetch_pages(self, fetcher: PoliteFetcher) -> list[Page]:
        return [Page(url=url, html=await fetcher.get(url)) for url in self.start_urls]

    def parse(self, page: Page) -> list[ObituaryEntry]:
        raise NotImplementedError
