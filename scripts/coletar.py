"""Monta a base de óbitos localmente, sem Docker: crawler e resolver no mesmo processo.

Uso:
    python scripts/coletar.py                          # coleta normal de todas as fontes
    python scripts/coletar.py --backfill               # percorre todo o histórico
    python scripts/coletar.py --backfill --max-pages 3 --fontes natal-leao-e-vila palmas-pax

Os registros ficam em um SQLite local (ignorado pelo git). Nunca publique esse arquivo:
ele contém dados pessoais e deve ser acessado só pela API, com finalidade e auditoria.
"""

import argparse
import asyncio
import sys
import time
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
for servico in ("crawler", "resolver"):
    sys.path.insert(0, str(RAIZ / "services" / servico))

from crawler_svc.config import CrawlerSettings  # noqa: E402
from crawler_svc.fetcher import PoliteFetcher  # noqa: E402
from crawler_svc.rawstore import MemoryRawStore  # noqa: E402
from crawler_svc.runner import run_spider  # noqa: E402
from crawler_svc.spiders import SPIDERS  # noqa: E402
from morbidus_common.bus import InMemoryBus  # noqa: E402
from morbidus_common.db import make_engine  # noqa: E402
from morbidus_common.events import Topics  # noqa: E402
from morbidus_common.logging import setup_logging  # noqa: E402
from morbidus_common.search import InMemoryDeathIndex  # noqa: E402
from resolver_svc.models import Base, DeathRecord  # noqa: E402
from resolver_svc.resolver import Resolver  # noqa: E402
from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fontes", nargs="*", default=[s for s in SPIDERS if s != "fixture"])
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--db", default=f"sqlite:///{RAIZ / 'morbidus_local.db'}")
    parser.add_argument("--delay", type=float, default=CrawlerSettings().request_delay_seconds)
    args = parser.parse_args()
    setup_logging("coletar", "INFO")

    engine = make_engine(args.db)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    bus = InMemoryBus()
    resolver = Resolver(sessions, InMemoryDeathIndex(), bus, window_days=3)
    bus.subscribe(Topics.OBITUARY_RAW, resolver.handle_obituary)
    # O barramento em memória guardaria todos os eventos; aqui não precisa.
    bus.published = _Descarte()

    ua = CrawlerSettings().user_agent
    inicio = time.monotonic()

    async def _uma(nome: str) -> tuple[str, int | str]:
        fetcher = PoliteFetcher(ua, args.delay)
        try:
            total = await run_spider(SPIDERS[nome](), fetcher, MemoryRawStore(), bus, args.backfill, args.max_pages)
            return nome, total
        except Exception as exc:
            return nome, f"erro: {exc!r}"
        finally:
            await fetcher.aclose()

    resultados = await asyncio.gather(*(_uma(n) for n in args.fontes))

    print(f"\nColeta concluída em {time.monotonic() - inicio:.0f}s")
    for nome, total in resultados:
        print(f"  {nome:32} {total}")
    with sessions() as db:
        total = db.scalar(select(func.count()).select_from(DeathRecord))
        por_uf = Counter(dict(db.execute(select(DeathRecord.uf, func.count()).group_by(DeathRecord.uf)).all()))
    print(f"\nRegistros únicos na base: {total}")
    for uf, n in por_uf.most_common():
        print(f"  {uf}: {n}")


class _Descarte(list):
    def append(self, item) -> None:
        pass


if __name__ == "__main__":
    asyncio.run(main())
