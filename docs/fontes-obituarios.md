# Fontes de obituário das 27 capitais

Mapeamento feito em outubro de 2026. Para cada capital: a melhor fonte web aberta, se existe, e o caminho para cobertura completa.

**Regras para uma fonte entrar como spider:**
- página pública, sem login, captcha ou paywall;
- `robots.txt` permitindo o caminho para o user-agent genérico (`MORBiDusBot` se identifica e não se passa por navegador);
- termos de uso sem proibição explícita de coleta;
- extração apenas de dados do falecido: nome, idade, datas e local. Parentes, endereço residencial, profissão e texto livre ficam de fora.

Fontes bloqueadas por `robots.txt` ou por termos de uso **não** são coletadas. Para elas, o caminho é institucional (pedido via LAI, convênio ou parceria).

Legenda: ✅ spider ativo · 🟡 fonte existe, spider pendente · ⛔ fonte bloqueada · ❌ sem fonte web aberta

## Resumo

| Capital | UF | Situação | Fonte ativa (`source_id`) | Histórico |
| --- | --- | --- | --- | --- |
| Rio Branco | AC | ❌ | | |
| Maceió | AL | ❌ | | |
| Macapá | AP | ❌ | | |
| Manaus | AM | 🟡 | Santa Rita / São Francisco (API fora do ar na verificação) | |
| Salvador | BA | ✅ | `salvador-campo-santo`, `salvador-bosque-da-paz` | meses / ~6 mil |
| Fortaleza | CE | ❌ | | |
| Brasília | DF | ✅ | `brasilia-correio-braziliense` | desde 2024 |
| Vitória | ES | 🟡 | A Gazeta (só pessoas notórias) | |
| Goiânia | GO | ✅ | `goiania-parque-memorial` (só o dia; a coleta forma o histórico) | desde out/2026 |
| São Luís | MA | ✅ | `saoluis-pax-uniao` (parado desde mai/2026) | ~900 de mar/2025 a mai/2026 |
| Cuiabá | MT | ✅ | `cuiaba-pax-nacional` (parado desde dez/2025) | ~26 mil de 2018 a dez/2025 |
| Campo Grande | MS | ✅ | `campogrande-a-critica` | desde set/2026 |
| Belo Horizonte | MG | ✅ | `bh-coracao-de-jesus` (volume baixo) | avisos recentes |
| Belém | PA | ❌ | | |
| João Pessoa | PB | 🟡 | `campinagrande-parque-da-paz` (Campina Grande, não a capital) | histórico do Memoriam |
| Curitiba | PR | ✅ | `curitiba-servico-funerario`, `curitiba-jardim-da-saudade` | 2 dias (prefeitura) e histórico (Jardim da Saudade) |
| Recife | PE | ❌ | | |
| Teresina | PI | ✅ | `teresina-pax-uniao` | ~3 semanas (coleta contínua) |
| Rio de Janeiro | RJ | ❌ | | |
| Natal | RN | ✅ | `natal-leao-e-vila` | ~1.240 desde 2025 |
| Porto Alegre | RS | ✅ | `portoalegre-angelus` | ~8.300 |
| Porto Velho | RO | ✅ | `portovelho-news-rondonia` | ~430 |
| Boa Vista | RR | ✅ | `boavista-orsolu` | histórico do Memoriam |
| Florianópolis | SC | ✅ | `florianopolis-jardim-da-paz` | só dias recentes |
| São Paulo | SP | ✅ | `saopaulo-chevra-kadisha` | mês corrente |
| Aracaju | SE | ❌ | | |
| Palmas | TO | ✅ | `palmas-pax` | ~3.900 desde 2021 |

**20 spiders ativos em 16 capitais, mais Campina Grande (PB).** Nenhuma prefeitura das 27 capitais publica lista de sepultados em formato aberto e coletável, exceto Curitiba. Campo Grande publica, mas bloqueia no `robots.txt`.

## Detalhe das fontes ativas

| `source_id` | URL | Campos | Observações |
| --- | --- | --- | --- |
| `curitiba-servico-funerario` | obituarios.curitiba.pr.gov.br/publico/falecimentos.aspx | nome, idade, falecimento, sepultamento (data e local) | Oficial. A página traz pai, mãe e cônjuge, que o parser descarta. Janela de 2 dias. |
| `portoalegre-angelus` | m.grupoangelus.com.br/f/322 | nome, **nascimento**, falecimento | Sistema Memoriam. Cobre a clientela da rede Angelus. |
| `natal-leao-e-vila` | sistemamemoriam.com/f/374 | nome, **nascimento**, falecimento | Sistema Memoriam, mesmo parser do Angelus. |
| `salvador-campo-santo` | cemiteriocamposanto.org.br/obituario | nome, idade, sepultamento | Endereço e procedência do falecido são descartados. |
| `salvador-bosque-da-paz` | bosquedapaz.com.br/wp-json/wp/v2/obituario | nome, data da cerimônia | API REST pública do WordPress. |
| `palmas-pax` | grupopaxpalmas.com.br/obituario | nome (às vezes abreviado), data | `robots.txt` bloqueia `/obito/`, então só a listagem é lida. Ordem crescente. |
| `portovelho-news-rondonia` | newsrondonia.com.br/obituario | nome, data de publicação | Lê só a listagem. Termos restringem uso a fins não comerciais (o MORBiDus é gratuito). |
| `saopaulo-chevra-kadisha` | chevrakadisha.org.br/preserve/historico-de-obitos | nome, idade, falecimento, sepultamento | Só a comunidade judaica. O filtro de histórico é JavaScript; por ora, só o mês corrente. |
| `florianopolis-jardim-da-paz` | cemiterioparquejardimdapaz.com.br/falecimentos | nome, falecimento | Publica só com consentimento da família; volume baixo. |
| `brasilia-correio-braziliense` | correiobraziliense.com.br (sitemaps) | nome, idade, cemitério, data | Coluna diária com os cemitérios do DF e de Valparaíso de Goiás. Backfill pelos sitemaps. |
| `campogrande-a-critica` | acritica.net/tag/sepultamentos | nome, idade, nascimento (às vezes), falecimento, destino | Republica o painel da prefeitura. Texto corrido, parser por regex. |

## Fontes bloqueadas (não coletar)

| Fonte | Motivo | Alternativa |
| --- | --- | --- |
| SCSWEB, Prefeitura de Campo Grande | `robots.txt` com `Disallow: /` | já coberto pelo A Crítica; pedir acesso formal |
| Páginas de detalhe do Pax Palmas | `robots.txt` bloqueia `/obito/` | a listagem basta para o matching |
| Bosque da Esperança (BH) | os dados vêm do Google Calendar, cujo `robots.txt` proíbe tudo; a página embute uma chave de API, que não usamos | pedir um feed autorizado |
| Parque Renascer (BH) | `robots.txt` proíbe o endpoint que entrega a agenda (`/wp-admin/admin-ajax.php`) | pedir autorização |
| Complexo Vale do Cerrado (Goiânia) | termos de uso proíbem copiar e redistribuir o conteúdo | pedir autorização: é a melhor fonte de Goiânia |
| CNF (Cadastro Nacional de Falecidos) | termos proíbem coleta e retransmissão por terceiros sem contrato | a fonte deles é a ABRASIF: parceria direta |
| Morada da Memória (Recife, Natal) | reCAPTCHA e só busca por nome | parceria com o Grupo Vila |
| Velórios online com senha (Zelo, Vale da Saudade e outras) | acesso restrito à família | não se aplica |

## Capitais sem fonte aberta: caminho institucional

| Capital | Quem tem o dado | Abordagem |
| --- | --- | --- |
| Rio de Janeiro | Rio Pax e Reviver (concessionárias); a prefeitura recebe dados diários por resolução de 2020 | LAI à secretaria responsável; convênio |
| São Paulo (cobertura geral) | Consolare, Cortel, Grupo Maya e Velar (concessionárias); SP Regula | convênio com as concessionárias |
| Belo Horizonte | Fundação de Parques Municipais e Zoobotânica (FPMZB) | LAI |
| Goiânia | Central de Óbitos da Prefeitura | LAI |
| Cuiabá | secretaria municipal responsável pelos cemitérios | LAI |
| Recife | Emlurb (Gerência de Necrópoles); Grupo Vila | LAI; parceria |
| Fortaleza, São Luís, Teresina, Maceió, Aracaju, João Pessoa | prefeituras e cemitérios parque locais | LAI; em João Pessoa, acompanhar o sistema Cemitech e a futura concessão |
| Belém, Macapá, Boa Vista, Rio Branco | secretarias de zeladoria e funerárias locais | LAI; parceria com funerárias |
| Brasília (fonte oficial) | Campo da Esperança (concessionária dos 6 cemitérios públicos) | parceria para feed oficial |
| Todas | ABRASIF, ALASIF, sindicatos de funerárias | parceria nacional, o mesmo modelo de onde o CNF tira os dados |

Pendências técnicas:
- **Manaus (Santa Rita / São Francisco):** a API da Santa Rita respondeu erro 522; tentar de novo e escrever o spider.
- **Sistema Memoriam:** atende várias funerárias como tenants. Os que usamos vieram de resultados de busca (Orsolu `/f/41`, Jardim da Saudade Curitiba `/f/306`, Pax União São Luís `/f/338`, Parque da Paz Campina Grande `/f/421`); não varremos IDs. Vale perguntar ao fornecedor (Trimarc) por outros nas capitais.
- **Adiaŭ** (velório online usado por Pax União e Vale da Saudade): robots.txt bloqueia `/embed` e os termos proíbem armazenar informações. Não coletar.
- **Cemitério Israelita:** histórico de 2006 a 2026 atrás de um filtro em JavaScript; investigar o endpoint.
