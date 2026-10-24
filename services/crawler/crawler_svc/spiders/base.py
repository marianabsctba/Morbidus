import logging
import re
from dataclasses import dataclass, field
from typing import AsyncIterator

import httpx

from crawler_svc.fetcher import PoliteFetcher

log = logging.getLogger(__name__)

DATA_BR = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


@dataclass
class Page:
    url: str
    html: str
    meta: dict = field(default_factory=dict)


@dataclass
class ObituaryEntry:
    """Só dados do falecido. Parentes citados no obituário nunca são extraídos (LGPD)."""

    nome: str
    idade: str | None = None
    data_nascimento: str | None = None
    data_falecimento: str | None = None
    data_sepultamento: str | None = None
    local: str | None = None
    # URL própria do registro, quando a fonte tem uma página por pessoa.
    url: str | None = None


class Spider:
    source_id: str
    cidade: str
    uf: str
    descricao: str = ""
    start_urls: list[str] = []

    async def iter_pages(
        self, fetcher: PoliteFetcher, backfill: bool = False, max_pages: int | None = None
    ) -> AsyncIterator[Page]:
        for url in self.start_urls:
            yield Page(url=url, html=await fetcher.get(url))

    def parse(self, page: Page) -> list[ObituaryEntry]:
        raise NotImplementedError


class PaginatedSpider(Spider):
    """Listagem paginada. Coleta normal lê as primeiras páginas; backfill segue até acabar."""

    first_page = 1
    incremental_pages = 2

    def page_url(self, n: int) -> str:
        raise NotImplementedError

    async def iter_pages(self, fetcher, backfill=False, max_pages=None):
        limite = (max_pages or 100_000) if backfill else self.incremental_pages
        for i in range(limite):
            url = self.page_url(self.first_page + i)
            try:
                page = Page(url=url, html=await fetcher.get(url))
            except httpx.HTTPStatusError as exc:
                # WordPress e afins respondem 400/404 depois da última página.
                if exc.response.status_code in (400, 404):
                    return
                raise
            if not self.parse(page):
                return
            yield page


def texto(tag) -> str | None:
    if tag is None:
        return None
    valor = " ".join(tag.get_text(" ", strip=True).split())
    return valor or None
