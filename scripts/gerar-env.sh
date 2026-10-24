#!/usr/bin/env bash
# Gera o .env de produção com segredos aleatórios. Rode na VPS, na raiz do repositório.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  echo ".env já existe. Apague ou edite à mão para não perder os segredos atuais."
  exit 1
fi

read -rp "Domínio (ex.: morbidus.besafe.academy): " DOMAIN
read -rp "E-mail para avisos do Let's Encrypt: " ACME_EMAIL
read -rp "IP de onde você vai administrar (ex.: 203.0.113.10): " ADMIN_IP

segredo() { openssl rand -hex 32; }

umask 077
cat > .env <<EOF
LOG_LEVEL=INFO

POSTGRES_USER=morbidus
POSTGRES_PASSWORD=$(segredo)

MINIO_ACCESS_KEY=morbidus
MINIO_SECRET_KEY=$(segredo)

ADMIN_TOKEN=$(segredo)
API_KEY_PEPPER=$(segredo)
AUDIT_CPF_SALT=$(segredo)

# Vazio até ter contrato com Serpro ou CRC. O mock nunca vai para produção.
ENABLED_PROVIDERS=

ENABLED_SPIDERS=all
CRAWL_INTERVAL_MINUTES=180

DOMAIN=${DOMAIN}
ACME_EMAIL=${ACME_EMAIL}
PUBLIC_ENTRYPOINT=websecure
ADMIN_ALLOWED_IPS=${ADMIN_IP}/32
EOF

echo
echo ".env criado com permissão 600."
echo "Guarde uma cópia do ADMIN_TOKEN e do API_KEY_PEPPER fora do servidor:"
echo "se o pepper mudar, todas as API keys emitidas deixam de funcionar."
