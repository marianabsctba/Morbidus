from bs4 import BeautifulSoup

from crawler_svc.spiders.base import ObituaryEntry, Page, Spider, texto

# Campos aproveitados. A página também traz pai, mãe, cônjuge e profissão,
# que ficam de fora de propósito (minimização, LGPD).
_CAMPOS = {
    "nome": "nome",
    "data do falecimento": "data_falecimento",
    "idade": "idade",
    "local do sepultamento": "local",
    "data do sepultamento": "data_sepultamento",
}


class CuritibaServicoFunerarioSpider(Spider):
    """Serviço Funerário Municipal. Mostra só os últimos 2 dias: coletar várias vezes ao dia."""

    source_id = "curitiba-servico-funerario"
    cidade = "Curitiba"
    uf = "PR"
    descricao = "Falecimentos dos últimos 2 dias, Serviço Funerário Municipal de Curitiba"
    start_urls = ["https://obituarios.curitiba.pr.gov.br/publico/falecimentos.aspx"]

    def parse(self, page: Page) -> list[ObituaryEntry]:
        soup = BeautifulSoup(page.html, "html.parser")
        tabela = soup.select_one("div.pagina_geral table")
        if tabela is None:
            return []
        registros: list[dict] = []
        for linha in tabela.find_all("tr"):
            celulas = linha.find_all("td")
            if len(celulas) != 2:
                continue
            rotulo = (texto(celulas[0]) or "").rstrip(":").strip().lower()
            if "item" in (linha.get("class") or []):
                registros.append({})
            if registros and rotulo in _CAMPOS:
                registros[-1][_CAMPOS[rotulo]] = texto(celulas[1])
        return [ObituaryEntry(**r) for r in registros if r.get("nome")]
