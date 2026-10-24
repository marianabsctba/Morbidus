from bs4 import BeautifulSoup

from crawler_svc.spiders.base import ObituaryEntry, Page, Spider, texto


class ChevraKadishaSpider(Spider):
    """Histórico de óbitos do mês corrente do Cemitério Israelita de São Paulo."""

    source_id = "saopaulo-chevra-kadisha"
    cidade = "São Paulo"
    uf = "SP"
    descricao = "Histórico de óbitos da Chevra Kadisha (Cemitério Israelita)"
    start_urls = ["https://chevrakadisha.org.br/preserve/historico-de-obitos"]

    def parse(self, page: Page) -> list[ObituaryEntry]:
        soup = BeautifulSoup(page.html, "html.parser")
        entries = []
        for linha in soup.select("table.table tbody tr"):
            # Colunas: falecido, falecimento, sepultamento, calendário judaico, idade.
            col = [texto(td) for td in linha.find_all("td")]
            if len(col) >= 5 and col[0]:
                entries.append(
                    ObituaryEntry(
                        nome=col[0],
                        data_falecimento=col[1],
                        data_sepultamento=col[2],
                        idade=col[4],
                        local="Cemitério Israelita",
                    )
                )
        return entries
