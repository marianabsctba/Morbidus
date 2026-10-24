import re
from datetime import date, timedelta

from bs4 import BeautifulSoup

from crawler_svc.spiders.base import ObituaryEntry, Page, Spider, texto

TAG = "https://acritica.net/tag/sepultamentos/"
_ARTIGO = re.compile(r'href="(https://acritica\.net/cidades/obituario-campo-grande-[^"#?]+)"')
_PUBLICADO = re.compile(r'"datePublished"\s*:\s*"(\d{4})-(\d{2})-(\d{2})')
_PESSOA = re.compile(
    r"^(?P<nome>[A-ZÀ-Ý][^,]{3,100}?)"
    r"(?:,\s*(?P<idade>\d{1,3})\s+anos)?"
    r"(?:,\s*nascid[oa]|,\s*nasceu)?(?:\s+em\s+(?P<nasc>\d{1,2} de [a-zç]+ de \d{4}))?"
    r",?\s+(?:e\s+)?morreu\b(?P<resto>[^.]*)"
)
_DIA = re.compile(r"\((\d{1,2})\)")


def _data_do_dia(dia: int, publicado: date) -> str:
    """O texto cita só o dia ("domingo (18)"); mês e ano vêm da publicação."""
    alvo = publicado.replace(day=1)
    if dia > publicado.day + 1:
        alvo = (alvo - timedelta(days=1)).replace(day=1)
    try:
        return alvo.replace(day=dia).strftime("%d/%m/%Y")
    except ValueError:
        return publicado.strftime("%d/%m/%Y")


class ACriticaCampoGrandeSpider(Spider):
    """Série do A Crítica que republica o painel de sepultamentos da prefeitura.

    O painel oficial (SCSWEB) tem robots.txt com Disallow: / e não é lido.
    """

    source_id = "campogrande-a-critica"
    cidade = "Campo Grande"
    uf = "MS"
    descricao = "Série Obituário Campo Grande do jornal A Crítica"

    async def iter_pages(self, fetcher, backfill=False, max_pages=None):
        limite = (max_pages or 1000) if backfill else 1
        vistos = set()
        for n in range(1, limite + 1):
            listagem = TAG if n == 1 else f"{TAG}page/{n}/"
            try:
                links = _ARTIGO.findall(await fetcher.get(listagem))
            except Exception:
                return
            novos = [u for u in dict.fromkeys(links) if u not in vistos]
            if not novos:
                return
            for url in novos:
                vistos.add(url)
                yield Page(url=url, html=await fetcher.get(url))

    def parse(self, page: Page) -> list[ObituaryEntry]:
        pub = _PUBLICADO.search(page.html)
        if not pub:
            return []
        publicado = date(*(int(x) for x in pub.groups()))
        corpo = BeautifulSoup(page.html, "html.parser").select_one("article")
        if corpo is None:
            return []
        entries, destino = [], None
        for el in corpo.find_all(["h3", "h4", "p"]):
            if el.name == "h4":
                destino = texto(el)
                continue
            if el.name != "p" or destino is None:
                continue
            m = _PESSOA.match(texto(el) or "")
            if not m or len(m.group("nome").split()) > 8:
                continue
            dia = _DIA.search(m.group("resto"))
            entries.append(
                ObituaryEntry(
                    nome=m.group("nome").strip(),
                    idade=f"{m.group('idade')} anos" if m.group("idade") else None,
                    data_nascimento=m.group("nasc"),
                    data_falecimento=_data_do_dia(int(dia.group(1)), publicado) if dia else None,
                    local=destino,
                    url=page.url,
                )
            )
        return entries
