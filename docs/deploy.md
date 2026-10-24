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
| `POSTGRES_PASSWORD`, `MINIO_SECRET_KEY` | senhas fortes e diferentes |
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

Crie o primeiro cliente e a API key (de um IP liberado em `ADMIN_ALLOWED_IPS`):

```bash
curl -X POST https://$DOMAIN/v1/admin/tenants -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"nome": "BeSafe"}'
curl -X POST https://$DOMAIN/v1/admin/tenants/<tenant_id>/api-keys -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"nome": "painel"}'
```

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

## Checklist antes de abrir para usuários

- [ ] Todos os segredos do `.env` trocados (nenhum `troque-...` sobrando)
- [ ] `ENABLED_PROVIDERS` vazio
- [ ] HTTPS funcionando e HTTP redirecionando
- [ ] `/v1/admin` respondendo 403 fora dos IPs liberados
- [ ] Backup diário dos volumes `pg-data` e `minio-data`
- [ ] Política de privacidade publicada explicando finalidade, base legal (prevenção à fraude, LGPD art. 7º, IX e art. 11, II, g) e canal do titular
- [ ] Encarregado (DPO) definido para atender pedidos de titulares
