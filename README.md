# MORBiDus

**Dead identities. Living fraud.**

Plataforma de **Death Identity Fraud Prevention (DIFP)**: identifica quando alguém tenta usar a identidade de uma pessoa falecida para abrir conta, tomar crédito, receber benefício ou acionar seguro.

O MORBiDus cruza duas camadas de dados:

| Camada | Fonte | Resultado |
| --- | --- | --- |
| Oficial | Provedores com CPF (Serpro, CRC Nacional; hoje um mock) | `obito_confirmado` |
| Obituários | Jornais e serviços funerários das capitais | `sinal_forte` ou `sinal_fraco`, com score |

Obituários não trazem CPF. Por isso, um match por obituário é sempre um **sinal de risco** a ser confirmado em fonte oficial, nunca um veredito.

## Arquitetura

```
Clientes (API) ──► Traefik (API key + rate limit) ──► query-svc ──► provider-svc
                              │                          │
                              └──► audit-svc             └──► OpenSearch
                                                               ▲
crawler-svc ──(obituary.raw)──► Kafka ──► resolver-svc ────────┘
     │                                         │
     └──► MinIO (HTML bruto)                   └──► Postgres
```

| Serviço | Papel |
| --- | --- |
| `identity` | Tenants, API keys (só o hash fica salvo) e o `forwardAuth` do gateway |
| `query` | Consulta por CPF e/ou nome, calcula o score e publica `query.performed` |
| `provider` | Interface única para provedores oficiais, com cache e circuit breaker |
| `crawler` | Um spider por fonte, respeita `robots.txt`, guarda o HTML bruto no MinIO |
| `resolver` | Normaliza nome, data e idade, junta a mesma pessoa vinda de fontes diferentes, indexa |
| `audit` | Trilha append-only de todas as consultas (trigger bloqueia UPDATE e DELETE) |

Infraestrutura: Traefik, Redpanda (compatível com Kafka), Postgres (um banco por serviço), OpenSearch, MinIO, Prometheus e Grafana.

## Rodando

```bash
cp .env.example .env
docker compose up -d --build
```

Criar um cliente e uma API key:

```bash
curl -X POST localhost:8080/v1/admin/tenants -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"nome": "Banco Exemplo"}'
curl -X POST localhost:8080/v1/admin/tenants/<tenant_id>/api-keys -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" -d '{"nome": "producao"}'
```

Coletar os obituários de exemplo (o crawler não fica exposto no gateway):

```bash
docker compose exec crawler python -c "import urllib.request as u; print(u.urlopen(u.Request('http://localhost:8000/v1/sources/fixture/run', method='POST')).read())"
```

Consultar:

```bash
curl -X POST localhost:8080/v1/consultas -H "X-API-Key: <chave>" -H "Content-Type: application/json" -d '{"nome": "Beltrana Ficticia de Souza", "uf": "PR", "cidade": "Curitiba", "finalidade": "onboarding"}'
```

O campo `finalidade` é obrigatório e fica registrado na auditoria (base legal na LGPD).

## Desenvolvimento sem Docker

Todos os serviços rodam com barramento e índice em memória, então os testes não precisam de infraestrutura:

```bash
python -m venv .venv
.venv/Scripts/pip install -e libs/morbidus-common "psycopg[binary]" httpx beautifulsoup4 minio "uvicorn[standard]" pytest pytest-asyncio
.venv/Scripts/python -m pytest
```

`tests/test_e2e.py` sobe crawler, resolver, query, provider e audit no mesmo processo e percorre o fluxo inteiro.

## Novas fontes de obituário

1. Crie uma classe em `services/crawler/crawler_svc/spiders/` herdando de `Spider`, com `source_id`, `cidade`, `uf`, `start_urls` e `parse`.
2. Registre em `SPIDERS` e habilite em `ENABLED_SPIDERS`.
3. Extraia **somente dados do falecido**: nome, idade, datas e local. Nomes de parentes e o texto do obituário nunca saem do HTML bruto.

Regras para fontes reais: respeitar `robots.txt` e os termos de uso do site, manter o intervalo entre requisições e preferir listas de serviços funerários e cemitérios municipais, que costumam ser mais estáveis que páginas de jornal.

## Próximos passos

- Mapear as fontes de obituário das 27 capitais e escrever os spiders
- Conectores Serpro e CRC Nacional quando houver contrato
- Painel web (React) para analistas
- `watchlist-svc`: monitorar CPFs e avisar por webhook quando surgir um óbito
- Migrações com Alembic, Redis para o cache do provider, Helm charts
