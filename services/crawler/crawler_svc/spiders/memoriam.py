"""Sistema Memoriam: plataforma de velório online usada por várias funerárias.

Cada funerária é um tenant (`/f/<id>`). Um mesmo parser atende todas.
"""

from bs4 import BeautifulSoup

from crawler_svc.spiders.base import DATA_BR, ObituaryEntry, Page, PaginatedSpider, texto


class MemoriamSpider(PaginatedSpider):
    base_url: str
    tenant_id: int

    def page_url(self, n: int) -> str:
        return f"{self.base_url}/f/{self.tenant_id}?page={n}"

    def parse(self, page: Page) -> list[ObituaryEntry]:
        soup = BeautifulSoup(page.html, "html.parser")
        entries = []
        for titulo in soup.select("div.grid h2"):
            card = titulo.find_parent("div", class_="rounded-lg")
            if card is None:
                continue
            datas = ["/".join(m) for m in DATA_BR.findall(card.get_text(" "))]
            link = card.select_one('a[href*="/c/"]')
            entries.append(
                ObituaryEntry(
                    nome=texto(titulo),
                    # O card mostra nascimento e depois falecimento.
                    data_nascimento=datas[0] if len(datas) >= 2 else None,
                    data_falecimento=datas[-1] if datas else None,
                    url=link["href"] if link else None,
                )
            )
        return entries


class AngelusPortoAlegreSpider(MemoriamSpider):
    source_id = "portoalegre-angelus"
    cidade = "Porto Alegre"
    uf = "RS"
    descricao = "Grupo Angelus, unidade Porto Alegre (Sistema Memoriam)"
    base_url = "https://m.grupoangelus.com.br"
    tenant_id = 322


class LeaoEVilaNatalSpider(MemoriamSpider):
    source_id = "natal-leao-e-vila"
    cidade = "Natal"
    uf = "RN"
    descricao = "Grupo Leão e Vila (Sistema Memoriam)"
    base_url = "https://sistemamemoriam.com"
    tenant_id = 374


class OrsoluBoaVistaSpider(MemoriamSpider):
    source_id = "boavista-orsolu"
    cidade = "Boa Vista"
    uf = "RR"
    descricao = "Funerária Orsolu (Sistema Memoriam)"
    base_url = "https://sistemamemoriam.com"
    tenant_id = 41


class PaxUniaoSaoLuisSpider(MemoriamSpider):
    """Sem novos registros desde maio de 2026; vale pelo histórico e caso volte a publicar."""

    source_id = "saoluis-pax-uniao"
    cidade = "São Luís"
    uf = "MA"
    descricao = "Grupo Pax União São Luís (Sistema Memoriam)"
    base_url = "https://sistemamemoriam.com"
    tenant_id = 338


class JardimDaSaudadeCuritibaSpider(MemoriamSpider):
    source_id = "curitiba-jardim-da-saudade"
    cidade = "Curitiba"
    uf = "PR"
    descricao = "Cemitério Jardim da Saudade de Curitiba (Sistema Memoriam)"
    base_url = "https://sistemamemoriam.com"
    tenant_id = 306


class ParqueDaPazCampinaGrandeSpider(MemoriamSpider):
    """Não é capital, mas é a única fonte aberta da Paraíba."""

    source_id = "campinagrande-parque-da-paz"
    cidade = "Campina Grande"
    uf = "PB"
    descricao = "Parque da Paz de Campina Grande (Sistema Memoriam)"
    base_url = "https://sistemamemoriam.com"
    tenant_id = 421
