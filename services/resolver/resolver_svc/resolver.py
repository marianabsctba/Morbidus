"""Transforma entradas brutas em registros de óbito únicos, juntando fontes da mesma pessoa."""

import asyncio
import logging

from morbidus_common.bus import EventBus
from morbidus_common.events import DeathRecordNormalized, ObituaryRaw, Topics
from morbidus_common.search import DeathIndex
from morbidus_common.text import normalize_name, phonetic_key, strip_accents
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from resolver_svc.models import DeathRecord, ProcessedEvent
from resolver_svc.parsing import parse_data, parse_idade

log = logging.getLogger(__name__)


def _cidade(texto: str) -> str:
    return strip_accents(texto).strip().lower()


def to_event(rec: DeathRecord) -> DeathRecordNormalized:
    return DeathRecordNormalized(
        record_id=rec.id,
        nome=rec.nome,
        nome_normalizado=rec.nome_normalizado,
        chave_fonetica=rec.chave_fonetica,
        idade=rec.idade,
        data_falecimento=rec.data_falecimento,
        ano_nascimento_estimado=rec.ano_nascimento_estimado,
        cidade=rec.cidade,
        uf=rec.uf,
        fontes=list(rec.fontes),
    )


class Resolver:
    def __init__(self, sessions: sessionmaker, index: DeathIndex, bus: EventBus, window_days: int) -> None:
        self._sessions = sessions
        self._index = index
        self._bus = bus
        self._window = window_days

    async def handle_obituary(self, payload: dict) -> None:
        raw = ObituaryRaw.model_validate(payload)
        record = await asyncio.to_thread(self.resolve, raw)
        if record is None:
            return
        await asyncio.to_thread(self._index.upsert, record)
        await self._bus.publish(Topics.DEATH_RECORD_NORMALIZED, record, key=record.record_id)

    def _find_match(self, db: Session, chave: str, raw: ObituaryRaw, data, idade) -> DeathRecord | None:
        candidatos = db.scalars(
            select(DeathRecord).where(DeathRecord.chave_fonetica == chave, DeathRecord.uf == raw.uf.upper())
        )
        for rec in candidatos:
            if _cidade(rec.cidade) != _cidade(raw.cidade):
                continue
            if data and rec.data_falecimento:
                if abs((rec.data_falecimento - data).days) <= self._window:
                    return rec
            elif idade is not None and rec.idade == idade:
                return rec
        return None

    def resolve(self, raw: ObituaryRaw) -> DeathRecordNormalized | None:
        with self._sessions() as db:
            if db.get(ProcessedEvent, raw.event_id):
                return None
            referencia = raw.occurred_at.date()
            data = parse_data(raw.data_falecimento, referencia) or parse_data(raw.data_sepultamento, referencia)
            idade = parse_idade(raw.idade)
            chave = phonetic_key(raw.nome)
            if not chave:
                log.warning("entrada sem nome aproveitável: %s", raw.event_id)
                db.add(ProcessedEvent(event_id=raw.event_id))
                db.commit()
                return None

            rec = self._find_match(db, chave, raw, data, idade)
            if rec is None:
                rec = DeathRecord(
                    nome=raw.nome.strip(),
                    nome_normalizado=normalize_name(raw.nome),
                    chave_fonetica=chave,
                    cidade=raw.cidade,
                    uf=raw.uf.upper(),
                    fontes=[],
                )
                db.add(rec)
            rec.idade = rec.idade if rec.idade is not None else idade
            rec.data_falecimento = rec.data_falecimento or data
            if rec.idade is not None:
                ano_base = rec.data_falecimento.year if rec.data_falecimento else referencia.year
                rec.ano_nascimento_estimado = ano_base - rec.idade
            if raw.source_url not in rec.fontes:
                # Reatribui a lista para o SQLAlchemy perceber a mudança no JSON.
                rec.fontes = [*rec.fontes, raw.source_url]
            db.add(ProcessedEvent(event_id=raw.event_id))
            db.commit()
            return to_event(rec)
