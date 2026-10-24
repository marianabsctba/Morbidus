#!/usr/bin/env bash
# Backup diário dos bancos do MORBiDus. Rode como root no servidor, na raiz do repositório,
# ou deixe o cron chamar (ver docs/deploy.md, seção Backup).
#
# Gera um .tar por dia em $DESTINO com um dump (formato custom do pg_dump) de cada banco,
# confere que cada dump pode ser lido pelo pg_restore e apaga os mais antigos que $DIAS.
# O HTML bruto não entra: é descartável e expira em 30 dias. O índice de busca é
# reconstruído a partir do banco (POST /interno/reindexar no resolver).
set -euo pipefail
cd "$(dirname "$0")/.."

DESTINO=${MORBIDUS_BACKUP_DIR:-/var/backups/morbidus}
DIAS=${MORBIDUS_BACKUP_DIAS:-14}
BANCOS=(identity resolver audit)
CARIMBO=$(date -u +%Y%m%dT%H%M%SZ)

umask 077
mkdir -p "$DESTINO"
TMP=$(mktemp -d "$DESTINO/.parcial-XXXXXX")
trap 'rm -rf "$TMP"' EXIT

for banco in "${BANCOS[@]}"; do
  docker compose exec -T postgres sh -c "pg_dump -U \"\$POSTGRES_USER\" -Fc -d $banco" </dev/null > "$TMP/$banco.dump"
  # Dump que o pg_restore não consegue listar não vale como backup.
  docker compose exec -T postgres pg_restore --list < "$TMP/$banco.dump" > /dev/null
done

tar -C "$TMP" -cf "$DESTINO/morbidus-$CARIMBO.tar" .
find "$DESTINO" -maxdepth 1 -name 'morbidus-*.tar' -mtime "+$DIAS" -delete

echo "backup ok: $DESTINO/morbidus-$CARIMBO.tar ($(du -h "$DESTINO/morbidus-$CARIMBO.tar" | cut -f1))"
