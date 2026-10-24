#!/usr/bin/env bash
# Liga a confirmação de e-mail do cadastro. Rode no servidor, na raiz do repositório:
#   ./scripts/configurar-smtp.sh
# A senha é pedida sem eco e vai direto para o .env (permissão 600); nunca aparece na tela.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "Rode ./scripts/gerar-env.sh antes."; exit 1; }

read -rp "Servidor SMTP [smtpout.secureserver.net]: " HOST
read -rp "Porta (465 = SSL, 587 = STARTTLS) [465]: " PORTA
read -rp "Usuário (e-mail da caixa que envia): " USUARIO
read -rsp "Senha da caixa (não aparece ao digitar): " SENHA; echo
read -rp "Domínio público do MORBiDus [https://morbidus.besafe.academy]: " URL
read -rp "Enviar e-mail de teste para: " TESTE

if [[ "$SENHA" == *"'"* ]]; then
  echo "Senhas com aspas simples (') não são suportadas no .env. Troque a senha da caixa e rode de novo."
  exit 1
fi

HOST=${HOST:-smtpout.secureserver.net}
PORTA=${PORTA:-465}
URL=${URL:-https://morbidus.besafe.academy}

definir() {
  local chave=$1 valor=$2
  local tmp
  tmp=$(mktemp)
  grep -v "^${chave}=" .env > "$tmp" || true
  # Aspas simples: o Compose não interpola $ nem corta em # dentro delas.
  printf "%s='%s'\n" "$chave" "$valor" >> "$tmp"
  cat "$tmp" > .env
  rm -f "$tmp"
}

umask 077
definir SMTP_HOST "$HOST"
definir SMTP_PORT "$PORTA"
definir SMTP_SSL "$([ "$PORTA" = 465 ] && echo true || echo false)"
definir SMTP_USER "$USUARIO"
definir SMTP_PASSWORD "$SENHA"
definir SMTP_FROM "MORBiDus <${USUARIO}>"
definir PUBLIC_URL "$URL"
unset SENHA

echo "Reiniciando o identity com a nova configuração..."
docker compose up -d identity >/dev/null 2>&1
for _ in $(seq 1 30); do
  docker compose ps identity --format '{{.Status}}' | grep -q healthy && break
  sleep 2
done

if docker compose exec -T identity python -m identity_svc.correio "$TESTE"; then
  echo "Pronto: novos cadastros vão precisar confirmar o e-mail."
else
  echo "O envio de teste falhou. Confira usuário, senha e porta e rode de novo."
  echo "Enquanto isso, os cadastros novos ficam pendentes de confirmação."
  exit 1
fi
