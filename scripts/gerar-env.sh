#!/usr/bin/env bash
# Gera o .env de produção com segredos aleatórios. Rode no servidor, na raiz do repositório.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  echo ".env já existe. Apague ou edite à mão para não perder os segredos atuais."
  exit 1
fi

read -rp "O servidor já tem nginx (ou outro proxy) nas portas 80/443? [s/N]: " ATRAS_DE_PROXY
segredo() { openssl rand -hex 32; }

if [[ "${ATRAS_DE_PROXY,,}" == s* ]]; then
  read -rp "Porta local para o MORBiDus [8090]: " PORTA
  REDE=$(cat <<EOF
# Atrás do nginx do host: veja infra/nginx/host-site.conf.example
TRAEFIK_BIND=127.0.0.1:${PORTA:-8090}
PUBLIC_ENTRYPOINT=web
EOF
)
else
  read -rp "Domínio (ex.: morbidus.besafe.academy): " DOMAIN
  read -rp "E-mail para avisos do Let's Encrypt: " ACME_EMAIL
  read -rp "IP de onde você vai administrar (ex.: 203.0.113.10): " ADMIN_IP
  REDE=$(cat <<EOF
# Traefik direto nas portas 80/443: use docker-compose.prod.yml
DOMAIN=${DOMAIN}
ACME_EMAIL=${ACME_EMAIL}
PUBLIC_ENTRYPOINT=websecure
ADMIN_ALLOWED_IPS=${ADMIN_IP}/32
EOF
)
fi

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

${REDE}
EOF

echo
echo ".env criado com permissão 600."
echo "Guarde uma cópia do ADMIN_TOKEN e do API_KEY_PEPPER fora do servidor:"
echo "se o pepper mudar, todas as API keys emitidas deixam de funcionar."
