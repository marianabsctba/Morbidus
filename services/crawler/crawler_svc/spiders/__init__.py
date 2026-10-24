from crawler_svc.spiders.base import ObituaryEntry, Page, Spider
from crawler_svc.spiders.fixture import FixtureSpider

# Cada fonte real (jornal ou serviço funerário de uma capital) vira uma classe
# registrada aqui, com source_id único.
SPIDERS: dict[str, type[Spider]] = {
    FixtureSpider.source_id: FixtureSpider,
}

__all__ = ["SPIDERS", "ObituaryEntry", "Page", "Spider"]
