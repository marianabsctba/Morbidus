# Deploy em produção

Guia para subir o MORBiDus num servidor com Docker, com HTTPS automático.

## O que precisa

- Servidor Linux com Docker e Docker Compose 2.24 ou mais novo, com no mínimo 4 GB de RAM (o OpenSearch sozinho reserva 512 MB de heap).
- Um nome de domínio apontando para o IP do servidor. Recomendado: subdomínio próprio, por exemplo `morbidus.besafe.academy`. Servir em subpasta (`besafe.academy/morbidus`) exige mudar a base do painel e as rotas do gateway.
- Portas 80 e 443 abertas.

## Passo a passo

```bash
git clone https://github.com/marianabsctba/Morbidus.git
cd Morbidus
cp .env.example .env
```

Edite o `.env`:

| Variável | Valor |
| --- | --- |
| `POSTGRES_PASSWORD` | senha forte |
| `ADMIN_TOKEN`, `API_KEY_PEPPER`, `AUDIT_CPF_SALT` | segredos longos e aleatórios (`openssl rand -hex 32`) |
| `ENABLED_PROVIDERS` | vazio (o mock não pode ir para produção) |
| `DOMAIN` | o domínio, por exemplo `morbidus.besafe.academy` |
| `ACME_EMAIL` | e-mail para avisos do Let's Encrypt |
| `PUBLIC_ENTRYPOINT` | `websecure` |
| `ADMIN_ALLOWED_IPS` | IP de onde você vai administrar, em formato CIDR |

Suba:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Crie sua conta pelo painel e promova-a a administradora, de dentro do servidor:

```bash
curl -X PATCH http://127.0.0.1:8090/v1/admin/usuarios/<seu-email> -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"admin": true, "email_verificado": true}'
```

Para exigir confirmação de e-mail no cadastro, rode `./scripts/configurar-smtp.sh`. Sem SMTP, as contas novas esperam aprovação na área de Administração.

Popular a base com o histórico das fontes (leva horas):

```bash
docker compose exec crawler python -c "import urllib.request as u; print(u.urlopen(u.Request('http://localhost:8000/v1/backfill', method='POST')).read())"
```

## Variante: servidor que já tem nginx nas portas 80/443

Comum quando o MORBiDus divide a máquina com outros sites. O Traefik escuta só em `127.0.0.1` e o nginx do host faz a ponte:

1. Rode `./scripts/gerar-env.sh` e responda **s** à primeira pergunta (gera `TRAEFIK_BIND=127.0.0.1:8090`).
2. Suba **sem** o overlay de produção: `docker compose up -d --build`.
3. Copie `infra/nginx/host-site.conf.example` para `/etc/nginx/sites-available/`, ajuste domínio e certificados, ligue em `sites-enabled` e rode `nginx -t && systemctl reload nginx`.
4. Crie o registro DNS do subdomínio (na Cloudflare, com proxy ligado).

Nessa variante, `/v1/admin` fica bloqueado no nginx. A administração é feita no próprio servidor, contra `http://127.0.0.1:8090`.

## Backup e restore

`scripts/backup.sh` faz o dump dos três bancos (contas, registros de óbito e auditoria) num `.tar` por dia em `/var/backups/morbidus` (só root lê), confere cada dump com `pg_restore --list` e guarda os últimos 14 dias. Instalação no cron do host:

```bash
echo '30 3 * * * root /opt/morbidus/scripts/backup.sh >> /var/log/morbidus-backup.log 2>&1' > /etc/cron.d/morbidus-backup
```

O backup fica na mesma máquina: protege contra erro e corrupção de dados, não contra perder o servidor. Copie os arquivos para fora (outro servidor ou armazenamento de objetos) assim que possível; eles têm dados pessoais, então cifre antes de enviar.

Para restaurar um banco (exemplo com o `resolver`):

```bash
tar -xf /var/backups/morbidus/morbidus-<data>.tar -C /tmp/restore
docker compose exec -T postgres sh -c 'dropdb -U "$POSTGRES_USER" resolver && createdb -U "$POSTGRES_USER" resolver'
docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d resolver --no-owner' < /tmp/restore/resolver.dump
docker compose exec -T resolver python -c "import urllib.request as u; print(u.urlopen(u.Request('http://localhost:8000/interno/reindexar', method='POST')).read())"
```

O último comando reconstrói o índice de busca do OpenSearch a partir do banco restaurado.

## Retenção

| Dado | Prazo | Onde |
| --- | --- | --- |
| Consultas, IP, user-agent e alertas | 2 anos (`AUDITORIA_RETENCAO_DIAS`, nunca menos de 180 dias) | rotina diária no audit-svc |
| HTML bruto das fontes | 30 dias (`RAW_RETENTION_DAYS`) | rotina do crawler |
| Backups | 14 dias (`MORBIDUS_BACKUP_DIAS`) | `scripts/backup.sh` |

A auditoria é append-only: um gatilho no Postgres bloqueia UPDATE e DELETE. A única exceção é a rotina de retenção, que marca a própria transação e só consegue apagar o que passou do prazo.

## Checklist antes de abrir para usuários

- [ ] Todos os segredos do `.env` trocados (nenhum `troque-...` sobrando)
- [ ] `ENABLED_PROVIDERS` vazio
- [ ] HTTPS funcionando e HTTP redirecionando
- [ ] `/v1/admin` respondendo 403 fora dos IPs liberados
- [x] Backup diário dos bancos (`scripts/backup.sh`) e cópia para fora do servidor
- [x] Política de privacidade e termos de uso em `/privacidade`, com aceite registrado e formulário para o encarregado
- [ ] Encarregado (DPO) definido para atender pedidos de titulares
