import json
import re

from bs4 import BeautifulSoup

from crawler_svc.spiders.base import ObituaryEntry, Page, Spider

SITE = "https://www.correiobraziliense.com.br"
_ARTIGO = re.compile(rf"<loc>({re.escape(SITE)}/cidades-df/\d{{4}}/\d{{2}}/\d+-obituario-[^<]+)</loc>")
_MAPA = re.compile(rf"<loc>({re.escape(SITE)}/sitemap/map/(\d+)\.xml)</loc>")
_ANO_URL = re.compile(r"/(20\d{2})/\d{2}/\d+-")
_LINHA = re.compile(
    r"^(?P<nome>[^,]{5,120}),\s*"
    r"(?P<idade>\d{1,3}\s*anos?|menos de (?:um|1) ano|idade n[aã]o informada)"
    r"\s*(?P<crem>\(crema[cç][aã]o\))?\.?$",
    re.I,
)
_DATA_EXTENSO = re.compile(r"\d{1,2} de [a-zç]+ de \d{4}", re.I)


def _article_ld(soup: BeautifulSoup) -> dict | None:
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            # O articleBody vem com quebras de linha cruas dentro da string.
            data = json.loads(script.string or "", strict=False)
        except ValueError:
            continue
        itens = data if isinstance(data, list) else data.get("@graph", [data])
        for item in itens:
            if isinstance(item, dict) and item.get("@type") == "NewsArticle" and item.get("articleBody"):
                return item
    return None


class CorreioBrazilienseSpider(Spider):
    """Coluna diária com os sepultamentos dos cemitérios do DF e de Valparaíso de Goiás."""

    source_id = "brasilia-correio-braziliense"
    cidade = "Brasília"
    uf = "DF"
    descricao = "Coluna diária de obituário do Correio Braziliense"
    backfill_desde = 2024

    async def _artigos_recentes(self, fetcher) -> list[str]:
        urls = []
        for mapa in ("sitemap/map/day/sitemap-news.xml", "sitemap/map/day/sitemap.xml"):
            urls += _ARTIGO.findall(await fetcher.get(f"{SITE}/{mapa}"))
        return urls

    async def _artigos_historicos(self, fetcher, max_pages: int | None):
        mapas: list[tuple[int, str]] = []
        for indice in ("sitemap/2.xml", "sitemap/1.xml"):
            mapas += [(int(n), url) for url, n in _MAPA.findall(await fetcher.get(f"{SITE}/{indice}"))]
        for _, url in sorted(mapas, reverse=True)[: max_pages or None]:
            xml = await fetcher.get(url)
            anos = [int(a) for a in _ANO_URL.findall(xml)]
            if anos and max(anos) < self.backfill_desde:
                return
            for artigo in _ARTIGO.findall(xml):
                yield artigo

    async def iter_pages(self, fetcher, backfill=False, max_pages=None):
        vistos = set()
        if backfill:
            fonte = self._artigos_historicos(fetcher, max_pages)
        else:
            async def _recentes():
                for u in await self._artigos_recentes(fetcher):
                    yield u
            fonte = _recentes()
        async for url in fonte:
            if url in vistos:
                continue
            vistos.add(url)
            yield Page(url=url, html=await fetcher.get(url))

    def parse(self, page: Page) -> list[ObituaryEntry]:
        artigo = _article_ld(BeautifulSoup(page.html, "html.parser"))
        if artigo is None:
            return []
        resumo = f"{artigo.get('alternateName', '')} {artigo.get('description', '')}"
        extenso = _DATA_EXTENSO.search(resumo)
        publicado = (artigo.get("datePublished") or "")[:10]
        data = extenso.group(0) if extenso else "/".join(reversed(publicado.split("-"))) or None
        entries, cemiterio = [], None
        for linha in (x.strip() for x in artigo["articleBody"].split("\n")):
            m = _LINHA.match(linha)
            if m:
                idade = m.group("idade").lower()
                idade = "0 anos" if idade.startswith("menos") else (None if "informada" in idade else idade)
                local = cemiterio
                if m.group("crem"):
                    local = f"{cemiterio} (cremação)" if cemiterio else "cremação"
                entries.append(ObituaryEntry(nome=m.group("nome").strip(), idade=idade, data_sepultamento=data, local=local))
            elif linha and len(linha) <= 60 and "," not in linha and not linha.endswith(":"):
                cemiterio = linha
        return entries
