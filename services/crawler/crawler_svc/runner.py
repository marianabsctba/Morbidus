import hashlib
import logging
from datetime import datetime, timezone

from morbidus_common.bus import EventBus
from morbidus_common.events import ObituaryRaw, Topics

from crawler_svc.fetcher import PoliteFetcher
from crawler_svc.rawstore import RawStore
from crawler_svc.spiders import Spider

log = logging.getLogger(__name__)


def _entry_id(source_id: str, nome: str, data: str | None) -> str:
    # Id determinístico: recoletar a mesma página não gera evento novo para o resolver.
    return hashlib.sha256(f"{source_id}|{nome}|{data or ''}".encode()).hexdigest()[:32]


async def run_spider(spider: Spider, fetcher: PoliteFetcher, store: RawStore, bus: EventBus) -> int:
    publicados = 0
    for page in await spider.fetch_pages(fetcher):
        html = page.html.encode("utf-8")
        hoje = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        key = f"{spider.source_id}/{hoje}/{hashlib.sha256(html).hexdigest()}.html"
        store.put(key, html)
        try:
            entries = spider.parse(page)
        except Exception:
            log.exception("falha ao interpretar %s (%s)", page.url, spider.source_id)
            continue
        for entry in entries:
            event = ObituaryRaw(
                event_id=_entry_id(spider.source_id, entry.nome, entry.data_falecimento),
                source_id=spider.source_id,
                source_url=page.url,
                cidade=spider.cidade,
                uf=spider.uf,
                nome=entry.nome,
                idade=entry.idade,
                data_falecimento=entry.data_falecimento,
                data_sepultamento=entry.data_sepultamento,
                local=entry.local,
                raw_object_key=key,
            )
            await bus.publish(Topics.OBITUARY_RAW, event, key=spider.source_id)
            publicados += 1
    log.info("spider %s publicou %d entradas", spider.source_id, publicados)
    return publicados
