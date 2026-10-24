"""Inteligência de ameaças em STIX 2.1, servida também por TAXII 2.1 (só leitura).

Só entram IPs de alertas que uma administradora confirmou como abuso: IP é dado
pessoal, e um falso positivo não pode parar no feed de outro CSIRT. Nenhum dado
de pessoa falecida ou consultada sai daqui.
"""

import ipaddress
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from audit_svc.models import Alerta, AuditEntry
from audit_svc.sentinela import ROTULOS

_NS = uuid.UUID("6d6f7262-6964-7573-2d63-74692d6e7330")
PRODUTOR = f"identity--{uuid.uuid5(_NS, 'morbidus')}"
# Marcação TLP:AMBER predefinida pela especificação STIX.
TLP_AMBER = "marking-definition--f88d31f6-486f-44da-b317-01333bde0b82"
COLECAO = str(uuid.uuid5(_NS, "abuso-confirmado"))
MEDIA_STIX = "application/stix+json;version=2.1"
MEDIA_TAXII = "application/taxii+json;version=2.1"


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _ts(dt: datetime) -> str:
    dt = _aware(dt)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def compartilhavel(endereco: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Só IPs roteáveis na internet: nada de rede interna, loopback ou faixas reservadas."""
    return endereco.is_global


def _ips_do_alerta(db: Session, alerta: Alerta) -> set[str]:
    if alerta.ip:
        return {alerta.ip}
    if not alerta.tenant_id:
        return set()
    inicio = alerta.criado_em - timedelta(hours=24)
    linhas = db.scalars(
        select(AuditEntry.ip_origem).where(
            AuditEntry.tenant_id == alerta.tenant_id,
            AuditEntry.ocorrido_em >= inicio,
            AuditEntry.ocorrido_em <= alerta.criado_em,
            AuditEntry.ip_origem.is_not(None),
        )
    )
    return set(linhas)


def objetos(db: Session, dias: int = 90, depois_de: datetime | None = None) -> list[dict]:
    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    alertas = db.scalars(
        select(Alerta).where(Alerta.status == "confirmado", Alerta.criado_em >= limite).order_by(Alerta.criado_em)
    ).all()
    por_ip: dict[str, dict] = {}
    for alerta in alertas:
        for ip in _ips_do_alerta(db, alerta):
            try:
                endereco = ipaddress.ip_address(ip)
            except ValueError:
                continue
            if not compartilhavel(endereco):
                continue
            item = por_ip.setdefault(ip, {"versao": endereco.version, "regras": set(), "primeiro": alerta.criado_em, "ultimo": alerta.criado_em})
            item["regras"].add(alerta.regra)
            item["primeiro"] = min(item["primeiro"], alerta.criado_em)
            item["ultimo"] = max(item["ultimo"], alerta.criado_em)

    saida = []
    for ip, item in sorted(por_ip.items()):
        modificado = _aware(item["ultimo"])
        if depois_de and modificado <= _aware(depois_de):
            continue
        rotulos = sorted(ROTULOS.get(r, r) for r in item["regras"])
        tipo = "ipv4-addr" if item["versao"] == 4 else "ipv6-addr"
        saida.append(
            {
                "type": "indicator",
                "spec_version": "2.1",
                "id": f"indicator--{uuid.uuid5(_NS, ip)}",
                "created": _ts(item["primeiro"]),
                "modified": _ts(modificado),
                "created_by_ref": PRODUTOR,
                "name": f"IP com abuso confirmado no MORBiDus: {ip}",
                "description": "Origem de consultas abusivas a uma base de identidades de pessoas falecidas: "
                + "; ".join(rotulos)
                + ". Confirmado manualmente pela administração do MORBiDus.",
                "indicator_types": ["anomalous-activity"],
                "pattern": f"[{tipo}:value = '{ip}']",
                "pattern_type": "stix",
                "valid_from": _ts(item["primeiro"]),
                "valid_until": _ts(modificado + timedelta(days=90)),
                "confidence": 80,
                "labels": sorted(item["regras"]),
                "object_marking_refs": [TLP_AMBER],
            }
        )
    return saida


def produtor_e_marcacao() -> list[dict]:
    return [
        {
            "type": "identity",
            "spec_version": "2.1",
            "id": PRODUTOR,
            "created": "2026-10-24T00:00:00.000Z",
            "modified": "2026-10-24T00:00:00.000Z",
            "name": "MORBiDus",
            "description": "Death Identity Fraud Prevention (BeSafe Academy)",
            "identity_class": "organization",
        },
        {
            "type": "marking-definition",
            "spec_version": "2.1",
            "id": TLP_AMBER,
            "created": "2017-01-20T00:00:00.000Z",
            "definition_type": "tlp",
            "name": "TLP:AMBER",
            "definition": {"tlp": "amber"},
        },
    ]


def pacote(db: Session) -> dict:
    return {
        "type": "bundle",
        "id": f"bundle--{uuid.uuid4()}",
        "objects": produtor_e_marcacao() + objetos(db),
    }
