"""Fontes de Belo Horizonte, Goiânia e Cuiabá."""

import re
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from crawler_svc.spiders.base import DATA_BR, ObituaryEntry, Page, PaginatedSpider, Spider, texto

_BRASILIA = timezone(timedelta(hours=-3))
_ANOS = re.compile(r"(\d{4})\s*-\s*(\d{4})")
_SEPULTAMENTO = re.compile(r"sepultamento[^0-9]{0,40}(\d{1,2}/\d{1,2}/\d{4})", re.I)


class PaxNacionalCuiabaSpider(PaginatedSpider):
    """Óbitos e memoriais da Pax Nacional. Cerca de 26 mil registros de 2018 a dez/2025;
    sem novidades desde então, vale pelo histórico e caso volte a publicar."""

    source_id = "cuiaba-pax-nacional"
    cidade = "Cuiabá"
    uf = "MT"
    descricao = "Óbitos e memoriais da Pax Nacional"
    por_pagina = 18

    def page_url(self, n: int) -> str:
        base = "https://www.paxnacional.com.br/obitos-memoriais"
        return base if n == 1 else f"{base}?start={(n - 1) * self.por_pagina}"

    def parse(self, page: Page) -> list[ObituaryEntry]:
        soup = BeautifulSoup(page.html, "html.parser")
        entries = []
        for item in soup.select("div.media"):
            link = item.select_one('h5 a[href*="/obitos-memoriais/item/"]')
            if link is None:
                continue
            nascimento = falecimento = None
            for small in item.select("p small"):
                data = DATA_BR.search(small.get_text())
                if data and small.select_one(".fa-star"):
                    nascimento = "/".join(data.groups())
                elif data and small.select_one(".fa-plus-circle"):
                    falecimento = "/".join(data.groups())
            entries.append(ObituaryEntry(nome=texto(link), data_nascimento=nascimento, data_falecimento=falecimento))
        return entries


class CoracaoDeJesusBHSpider(Spider):
    """Funerária Coração de Jesus, página de Belo Horizonte. Mostra os avisos mais recentes."""

    source_id = "bh-coracao-de-jesus"
    cidade = "Belo Horizonte"
    uf = "MG"
    descricao = "Avisos de falecimento da Funerária Coração de Jesus (Belo Horizonte)"
    start_urls = ["https://www.funerariacoracaodejesus.com.br/obituarios/belo-horizonte"]

    def parse(self, page: Page) -> list[ObituaryEntry]:
        soup = BeautifulSoup(page.html, "html.parser")
        entries = []
        for item in soup.select("div.obituario_item"):
            nome = texto(item.select_one(".name"))
            if not nome:
                continue
            anos = _ANOS.search(texto(item.select_one(".dates")) or "")
            sepultamento = _SEPULTAMENTO.search(texto(item.select_one(".text")) or "")
            link = item.select_one("a.link")
            entries.append(
                ObituaryEntry(
                    nome=nome,
                    # Só os anos aparecem: a idade sai com até um ano de diferença.
                    idade=f"{int(anos.group(2)) - int(anos.group(1))} anos" if anos else None,
                    data_sepultamento=sepultamento.group(1) if sepultamento else None,
                    url=link["href"] if link else None,
                )
            )
        return entries


class ParqueMemorialGoianiaSpider(Spider):
    """"Acontece Hoje" do Parque Memorial de Goiânia: só os sepultamentos do dia, sem data
    na página. A data registrada é a da coleta, então a fonte depende da coleta diária."""

    source_id = "goiania-parque-memorial"
    cidade = "Goiânia"
    uf = "GO"
    descricao = "Sepultamentos do dia no Parque Memorial de Goiânia"
    start_urls = ["https://parquememorialdegoiania.com.br/acontece_hoje/"]

    def parse(self, page: Page) -> list[ObituaryEntry]:
        hoje = datetime.now(_BRASILIA).strftime("%d/%m/%Y")
        linhas = BeautifulSoup(page.html, "html.parser").get_text("\n", strip=True).split("\n")
        entries = []
        for i, linha in enumerate(linhas):
            if not re.fullmatch(r"SALA\s*\d+", linha.strip(), re.I) or i == 0:
                continue
            nome = linhas[i - 1].strip()
            if sum(c.isalpha() for c in nome) >= 5 and nome.upper() == nome:
                entries.append(ObituaryEntry(nome=nome, data_sepultamento=hoje, local=f"Parque Memorial, {linha.strip().title()}"))
        return entries
