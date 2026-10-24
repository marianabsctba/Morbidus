import html
import json

from bs4 import BeautifulSoup

from crawler_svc.spiders.base import DATA_BR, ObituaryEntry, Page, PaginatedSpider, texto


class CampoSantoSpider(PaginatedSpider):
    source_id = "salvador-campo-santo"
    cidade = "Salvador"
    uf = "BA"
    descricao = "Obituário do Cemitério Campo Santo"

    def page_url(self, n: int) -> str:
        return f"https://www.cemiteriocamposanto.org.br/obituario/index.html?pag={n}"

    def parse(self, page: Page) -> list[ObituaryEntry]:
        soup = BeautifulSoup(page.html, "html.parser")
        entries = []
        for item in soup.select("div.Obi_Are_Ite"):
            campos = {}
            for bloco in item.select("div.Obi_Are_Ite_Inf > div"):
                rotulo = texto(bloco.select_one(".Obi_Are_Ite_Inf_Tit"))
                if rotulo:
                    campos[rotulo.lower()] = texto(bloco.select_one(".Obi_Are_Ite_Inf_Des"))
            # Endereço residencial e procedência ficam de fora (minimização).
            if campos.get("falecido"):
                entries.append(
                    ObituaryEntry(
                        nome=campos["falecido"],
                        idade=campos.get("idade"),
                        data_sepultamento=campos.get("sepultamento"),
                        local="Cemitério Campo Santo",
                    )
                )
        return entries


class BosqueDaPazSpider(PaginatedSpider):
    """Usa a API REST pública do WordPress do cemitério, mais estável que o HTML."""

    source_id = "salvador-bosque-da-paz"
    cidade = "Salvador"
    uf = "BA"
    descricao = "Obituário do Cemitério Bosque da Paz (API WordPress)"
    incremental_pages = 1

    def page_url(self, n: int) -> str:
        return f"https://bosquedapaz.com.br/wp-json/wp/v2/obituario?per_page=100&page={n}&_fields=title,content,link"

    def parse(self, page: Page) -> list[ObituaryEntry]:
        entries = []
        for post in json.loads(page.html):
            nome = html.unescape(post["title"]["rendered"]).strip()
            data = DATA_BR.search(BeautifulSoup(post["content"]["rendered"], "html.parser").get_text())
            entries.append(
                ObituaryEntry(
                    nome=nome,
                    data_sepultamento="/".join(data.groups()) if data else None,
                    local="Cemitério Bosque da Paz",
                    url=post.get("link"),
                )
            )
        return entries
