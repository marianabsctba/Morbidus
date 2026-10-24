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

## Checklist antes de abrir para usuários

- [ ] Todos os segredos do `.env` trocados (nenhum `troque-...` sobrando)
- [ ] `ENABLED_PROVIDERS` vazio
- [ ] HTTPS funcionando e HTTP redirecionando
- [ ] `/v1/admin` respondendo 403 fora dos IPs liberados
- [ ] Backup diário dos volumes `pg-data` e `minio-data`
- [ ] Política de privacidade publicada explicando finalidade, base legal (prevenção à fraude, LGPD art. 7º, IX e art. 11, II, g) e canal do titular
- [ ] Encarregado (DPO) definido para atender pedidos de titulares
