"""Parsers das fontes reais contra fixtures com a mesma marcação e pessoas fictícias."""

import json
from pathlib import Path

import httpx
from crawler_svc.fetcher import PoliteFetcher
from crawler_svc.rawstore import MemoryRawStore
from crawler_svc.runner import run_spider
from crawler_svc.spiders import SPIDERS, Page
from morbidus_common.bus import InMemoryBus

FIXTURES = Path(__file__).parent / "fixtures"


def _parse(source_id: str, fixture: str, url: str = "https://exemplo/pagina"):
    return SPIDERS[source_id]().parse(Page(url=url, html=(FIXTURES / fixture).read_text(encoding="utf-8")))


def _fetcher(rotas: dict[str, str | int]) -> PoliteFetcher:
    """Servidor falso: URL exata -> corpo, ou código de status."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        resposta = rotas.get(str(request.url))
        if resposta is None:
            return httpx.Response(404)
        if isinstance(resposta, int):
            return httpx.Response(resposta)
        return httpx.Response(200, text=resposta, headers={"content-type": "text/html; charset=utf-8"})

    return PoliteFetcher("teste", 0, client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def test_curitiba_ignora_parentes_e_profissao():
    entries = _parse("curitiba-servico-funerario", "curitiba.html")
    nomes = [e.nome for e in entries]
    assert nomes == ["JOAQUINA FICTICIA DOS EXEMPLOS", "NATIMORTO DE MAE FICTICIA", "SEVERINO EXEMPLAR DA SILVA"]
    primeiro = entries[0]
    assert primeiro.idade == "82 ano(s)"
    assert primeiro.data_falecimento == "sábado, 24 de outubro de 2026"
    assert primeiro.local == "CEMITÉRIO MUNICIPAL EXEMPLO"
    assert "PAI FICTICIO" not in str(entries) and "CONJUGE" not in str(entries) and "PROFESSOR" not in str(entries)


async def test_runner_descarta_natimorto():
    bus = InMemoryBus()
    url = SPIDERS["curitiba-servico-funerario"].start_urls[0]
    fetcher = _fetcher({url: (FIXTURES / "curitiba.html").read_text(encoding="utf-8")})
    total = await run_spider(SPIDERS["curitiba-servico-funerario"](), fetcher, MemoryRawStore(), bus)
    assert total == 2
    assert all("NATIMORTO" not in p["nome"] for _, p in bus.published)


def test_memoriam_traz_nascimento_e_falecimento():
    entries = _parse("natal-leao-e-vila", "memoriam.html")
    assert [(e.nome, e.data_nascimento, e.data_falecimento) for e in entries] == [
        ("BENEDITO EXEMPLO FICTICIO", "22/02/1950", "24/10/2026"),
        ("MARIA DAS DORES DE TESTE", "13/06/1939", "23/10/2026"),
    ]
    assert entries[0].url == "https://sistemamemoriam.com/c/1001"


def test_campo_santo_nao_extrai_endereco():
    (entry,) = _parse("salvador-campo-santo", "campo_santo.html")
    assert entry.nome == "VALDOMIRA FICTICIA SOARES"
    assert entry.idade == "87 anos"
    assert entry.data_sepultamento == "24/10/2026 às 16:45"
    assert "Bairro Exemplo" not in str(entry) and "Hospital" not in str(entry)


def test_bosque_da_paz_decodifica_entidades_html():
    entries = _parse("salvador-bosque-da-paz", "bosque_da_paz.json")
    assert entries[0].nome == "LAURINDA FICTÍCIA RIBEIRO"
    assert entries[0].data_sepultamento == "23/10/2026"


def test_pax_palmas_separa_nome_da_data():
    entries = _parse("palmas-pax", "pax_palmas.html")
    assert [(e.nome, e.data_falecimento) for e in entries] == [
        ("Ana M. P. Exemplo", "26/11/2021"),
        ("Raimundo Teste Lima", "27/11/2021"),
    ]


def test_news_rondonia_usa_titulo_e_data_da_url():
    entries = _parse("portovelho-news-rondonia", "news_rondonia.html")
    assert [(e.nome, e.data_sepultamento) for e in entries] == [
        ("Maria Luiza Fictícia", "23/10/2026"),
        ("Paulo de Teste", "07/10/2026"),
    ]


def test_chevra_kadisha():
    entries = _parse("saopaulo-chevra-kadisha", "chevra_kadisha.html")
    assert (entries[0].nome, entries[0].data_falecimento, entries[0].idade) == ("RENATO EXEMPLO COHEN", "21/10/2026", "87")


def test_jardim_da_paz_ignora_menu():
    entries = _parse("florianopolis-jardim-da-paz", "jardim_da_paz.html")
    assert [(e.nome, e.data_falecimento) for e in entries] == [
        ("ROBERTO EXEMPLO NOGUEIRA", "22/10/2026"),
        ("LUCIA DE TESTE MACIEL", "21/10/2026"),
    ]


def test_correio_braziliense_agrupa_por_cemiterio():
    entries = _parse("brasilia-correio-braziliense", "correio_braziliense.html")
    resumo = [(e.nome, e.idade, e.local) for e in entries]
    assert resumo == [
        ("Benedito Exemplo Correia", "90 anos", "Campo da Esperança"),
        ("Bernardo Teste da Silva", None, "Campo da Esperança"),
        ("Gael Ficticio Rodrigues", "0 anos", "Campo da Esperança"),
        ("Arlinda Exemplo dos Santos", "79 anos", "Taguatinga (cremação)"),
    ]
    assert {e.data_sepultamento for e in entries} == {"23 de outubro de 2026"}


def test_a_critica_extrai_do_texto_corrido():
    entries = _parse("campogrande-a-critica", "a_critica.html", url="https://acritica.net/cidades/obituario-x/")
    resumo = [(e.nome, e.idade, e.data_nascimento, e.data_falecimento, e.local) for e in entries]
    assert resumo == [
        ("Edgar Exemplo Rodrigues", None, None, "18/10/2026", "Crematório Campo Grande"),
        ("Valeria Ficticia de Araujo", "57 anos", "13 de setembro de 1969", "18/10/2026", "Cemitério Jardim da Paz"),
        ("Isis Helena de Teste", None, None, "17/10/2026", "Cemitério Memorial Park"),
        # Dia maior que o da publicação: é do mês anterior.
        ("Antonio Marcos Exemplo", None, None, "30/09/2026", "Cemitério Memorial Park"),
    ]


async def test_paginacao_para_na_pagina_vazia():
    spider = SPIDERS["natal-leao-e-vila"]()
    cheia = (FIXTURES / "memoriam.html").read_text(encoding="utf-8")
    fetcher = _fetcher({spider.page_url(1): cheia, spider.page_url(2): cheia, spider.page_url(3): "<html></html>"})
    paginas = [p.url async for p in spider.iter_pages(fetcher, backfill=True)]
    assert paginas == [spider.page_url(1), spider.page_url(2)]
    incremental = [p.url async for p in spider.iter_pages(fetcher)]
    assert len(incremental) == spider.incremental_pages


async def test_bosque_da_paz_para_no_400_do_wordpress():
    spider = SPIDERS["salvador-bosque-da-paz"]()
    corpo = (FIXTURES / "bosque_da_paz.json").read_text(encoding="utf-8")
    fetcher = _fetcher({spider.page_url(1): corpo, spider.page_url(2): 400})
    assert len([p async for p in spider.iter_pages(fetcher, backfill=True)]) == 1


async def test_pax_palmas_incremental_le_as_ultimas_paginas():
    spider = SPIDERS["palmas-pax"]()
    corpo = (FIXTURES / "pax_palmas.html").read_text(encoding="utf-8")
    fetcher = _fetcher({spider.page_url(n): corpo for n in range(1, 6)})
    incremental = [p.url async for p in spider.iter_pages(fetcher)]
    assert incremental == [spider.page_url(4), spider.page_url(5)]
    completo = [p.url async for p in spider.iter_pages(fetcher, backfill=True)]
    assert completo == [spider.page_url(n) for n in range(1, 6)]


async def test_correio_backfill_para_quando_o_sitemap_fica_antigo():
    site = "https://www.correiobraziliense.com.br"
    artigo = f"{site}/cidades-df/2025/03/7000001-obituario-30-funerais-nesta-terca.html"
    antigo = f"{site}/cidades-df/2019/03/1000001-obituario-30-funerais.html"

    def mapa(*locs):
        return "<urlset>" + "".join(f"<url><loc>{u}</loc></url>" for u in locs) + "</urlset>"

    rotas = {
        f"{site}/sitemap/2.xml": f"<sitemapindex><sitemap><loc>{site}/sitemap/map/12.xml</loc></sitemap></sitemapindex>",
        f"{site}/sitemap/1.xml": f"<sitemapindex><sitemap><loc>{site}/sitemap/map/11.xml</loc></sitemap></sitemapindex>",
        f"{site}/sitemap/map/12.xml": mapa(artigo, f"{site}/politica/2025/03/7000002-outra-noticia.html"),
        f"{site}/sitemap/map/11.xml": mapa(antigo),
        artigo: (FIXTURES / "correio_braziliense.html").read_text(encoding="utf-8"),
    }
    spider = SPIDERS["brasilia-correio-braziliense"]()
    paginas = [p.url async for p in spider.iter_pages(_fetcher(rotas), backfill=True)]
    assert paginas == [artigo]


def test_todas_as_fontes_tem_metadados():
    for source_id, cls in SPIDERS.items():
        assert cls.source_id == source_id
        assert cls.cidade and len(cls.uf) == 2 and cls.descricao, source_id


def test_fixture_json_e_valida():
    json.loads((FIXTURES / "bosque_da_paz.json").read_text(encoding="utf-8"))


def test_pax_uniao_teresina():
    entries = _parse("teresina-pax-uniao", "pax_uniao_teresina.html")
    assert [(e.nome, e.data_nascimento, e.data_falecimento, e.data_sepultamento, e.local) for e in entries] == [
        ("GENOVEVA FICTICIA OLIVEIRA", "25/08/1942", "24/10/2026", "24/10/2026", "JARDIM II"),
        ("MANOEL DE TESTE MELLO", "13/11/1939", "23/10/2026", None, None),
    ]


async def test_fetchers_diferentes_dividem_o_ritmo_do_mesmo_site():
    import time

    from crawler_svc.fetcher import PoliteFetcher

    PoliteFetcher._ultimo_acesso.clear()
    rotas = {"https://memoriam.exemplo/f/1": "a", "https://memoriam.exemplo/f/2": "b"}
    a, b = _fetcher(rotas), _fetcher(rotas)
    a._delay = b._delay = 0.3
    inicio = time.monotonic()
    await a.get("https://memoriam.exemplo/f/1")
    await b.get("https://memoriam.exemplo/f/2")
    # O segundo spider espera o intervalo do primeiro, mesmo sendo outro fetcher.
    assert time.monotonic() - inicio >= 0.3
