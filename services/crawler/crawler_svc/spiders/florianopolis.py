from bs4 import BeautifulSoup

from crawler_svc.spiders.base import DATA_BR, ObituaryEntry, Page, Spider


class JardimDaPazSpider(Spider):
    """Página feita em Elementor, sem classes estáveis: o parser segue a sequência do texto.

    O cemitério só publica com consentimento da família.
    """

    source_id = "florianopolis-jardim-da-paz"
    cidade = "Florianópolis"
    uf = "SC"
    descricao = "Falecimentos do Cemitério Parque Jardim da Paz"
    start_urls = ["https://cemiterioparquejardimdapaz.com.br/falecimentos/"]

    def parse(self, page: Page) -> list[ObituaryEntry]:
        linhas = BeautifulSoup(page.html, "html.parser").get_text("\n", strip=True).split("\n")
        entries = []
        for i, linha in enumerate(linhas):
            # Rótulo exato: o menu do site também tem um item "Falecimentos".
            if linha.rstrip(":").strip() != "Falecimento" or i == 0:
                continue
            nome = linhas[i - 1].strip()
            data = next((DATA_BR.search(x) for x in linhas[i : i + 3] if DATA_BR.search(x)), None)
            if sum(c.isalpha() for c in nome) >= 5 and nome.upper() == nome:
                entries.append(
                    ObituaryEntry(
                        nome=nome,
                        data_falecimento="/".join(data.groups()) if data else None,
                        local="Cemitério Parque Jardim da Paz",
                    )
                )
        return entries
