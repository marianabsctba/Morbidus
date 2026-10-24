from crawler_svc.spiders.base import ObituaryEntry, Page, PaginatedSpider, Spider
from crawler_svc.spiders.brasilia import CorreioBrazilienseSpider
from crawler_svc.spiders.campogrande import ACriticaCampoGrandeSpider
from crawler_svc.spiders.curitiba import CuritibaServicoFunerarioSpider
from crawler_svc.spiders.fixture import FixtureSpider
from crawler_svc.spiders.florianopolis import JardimDaPazSpider
from crawler_svc.spiders.memoriam import AngelusPortoAlegreSpider, LeaoEVilaNatalSpider
from crawler_svc.spiders.palmas import PaxPalmasSpider
from crawler_svc.spiders.portovelho import NewsRondoniaSpider
from crawler_svc.spiders.salvador import BosqueDaPazSpider, CampoSantoSpider
from crawler_svc.spiders.saopaulo import ChevraKadishaSpider

# Uma classe por fonte, com source_id único. Ver docs/fontes-obituarios.md.
SPIDERS: dict[str, type[Spider]] = {
    s.source_id: s
    for s in (
        FixtureSpider,
        CuritibaServicoFunerarioSpider,
        AngelusPortoAlegreSpider,
        LeaoEVilaNatalSpider,
        CampoSantoSpider,
        BosqueDaPazSpider,
        PaxPalmasSpider,
        NewsRondoniaSpider,
        ChevraKadishaSpider,
        JardimDaPazSpider,
        CorreioBrazilienseSpider,
        ACriticaCampoGrandeSpider,
    )
}

__all__ = ["SPIDERS", "ObituaryEntry", "Page", "PaginatedSpider", "Spider"]
