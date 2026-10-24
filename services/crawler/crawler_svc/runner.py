import hashlib
import logging
import re
from datetime import datetime, timezone

from morbidus_common.bus import EventBus
from morbidus_common.events import ObituaryRaw, Topics
from morbidus_common.text import normalize_name

from crawler_svc.fetcher import PoliteFetcher
from crawler_svc.rawstore import RawStore
from crawler_svc.spiders import ObituaryEntry, Spider

log = logging.getLogger(__name__)

# Registros que não identificam uma pessoa e só gerariam falso positivo.
# Compara com o nome normalizado (sem acento e sem "de/da/do"), por isso "RN de Maria" vira "rn maria".
_NOMES_DESCARTADOS = re.compile(r"natimort|nao identificad|desconhecid|indigente|\bfeto\b|^rn\b|recem nascido")


def _entry_id(source_id: str, nome: str, data: str | None) -> str:
    # Id determinístico: recoletar a mesma página não gera evento novo para o resolver.
    return hashlib.sha256(f"{source_id}|{nome}|{data or ''}".encode()).hexdigest()[:32]


def nome_aproveitavel(nome: str | None) -> bool:
    if not nome:
        return False
    normalizado = normalize_name(nome)
    return len(normalizado.split()) >= 2 and not _NOMES_DESCARTADOS.search(normalizado)


async def run_spider(
    spider: Spider,
    fetcher: PoliteFetcher,
    store: RawStore,
    bus: EventBus,
    backfill: bool = False,
    max_pages: int | None = None,
) -> int:
    publicados = 0
    async for page in spider.iter_pages(fetcher, backfill=backfill, max_pages=max_pages):
        conteudo = page.html.encode("utf-8")
        hoje = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        key = f"{spider.source_id}/{hoje}/{hashlib.sha256(conteudo).hexdigest()}.html"
        store.put(key, conteudo)
        try:
            entries: list[ObituaryEntry] = spider.parse(page)
        except Exception:
            log.exception("falha ao interpretar %s (%s)", page.url, spider.source_id)
            continue
        for entry in entries:
            if not nome_aproveitavel(entry.nome):
                continue
            data_ref = entry.data_falecimento or entry.data_sepultamento
            event = ObituaryRaw(
                event_id=_entry_id(spider.source_id, entry.nome, data_ref),
                source_id=spider.source_id,
                source_url=entry.url or page.url,
                cidade=spider.cidade,
                uf=spider.uf,
                nome=entry.nome,
                idade=entry.idade,
                data_nascimento=entry.data_nascimento,
                data_falecimento=entry.data_falecimento,
                data_sepultamento=entry.data_sepultamento,
                local=entry.local,
                raw_object_key=key,
            )
            await bus.publish(Topics.OBITUARY_RAW, event, key=spider.source_id)
            publicados += 1
    log.info("spider %s publicou %d entradas (backfill=%s)", spider.source_id, publicados, backfill)
    return publicados
