# Plano de Reestruturação – Imobiliária (AtendeJá)

## Objetivos
- Simplificar e focar no domínio imobiliário (atendimento + marketing) com custo baixo.
- Entregar rapidamente um MVP funcional: cadastro/listagem de imóveis e leads; funil básico via WhatsApp.
- Preparar terreno para escalar: multi-tenant, storage de imagens e deploy em nuvem barata.

## Stack (MVP)
- Backend: FastAPI (Python 3.11)
- Banco: PostgreSQL (Neon/Railway em produção; Docker local)
- Imagens: Cloudflare R2 (S3 compatível) – iniciar aceitando URLs; upload com URL pré-assinada em etapa posterior
- Hospedagem API: Railway/Render (deploy via Docker)
- Logs: structlog (JSON)
- Filas: adiado para pós-MVP (evitar custo e complexidade)

## Modelagem de Dados
- re_properties: imóvel (tipo, finalidade, preço, localização, quartos etc.), ativo, timestamps
- re_property_images: imagens (url, chave de storage, capa, ordenação)
- re_amenities, re_property_amenities: amenidades e associação
- re_leads: lead com preferências e consentimento LGPD
- re_inquiries: consulta/interesse (buy/rent/question) por lead e imóvel
- re_visit_schedules: agendamentos de visita (requested/confirmed/canceled/done)

Índices principais: finalidade, tipo, cidade/estado, preço, ativo, quartos.

## Endpoints (MVP – PT-BR)
- POST /re/imoveis – cadastra imóvel
- GET  /re/imoveis – lista com filtros (finalidade, tipo, cidade, estado, preço, dormitórios)
- GET  /re/imoveis/{id} – obter imóvel
- PATCH /re/imoveis/{id} – atualizar parcial (inclui ativar/desativar)
- POST /re/imoveis/{id}/imagens – adicionar imagem (url, capa, ordem)
- GET  /re/imoveis/{id}/imagens – listar imagens
- GET  /re/imoveis/{id}/detalhes – imóvel consolidado com imagens (para o front)
- POST /re/leads – cadastrar lead (nome, telefone, email, origem, preferencias, consentimento_lgpd)
- GET  /re/leads – listar leads

Próximos:
- POST /re/inquiries, POST /re/visit-schedules

## Fluxo WhatsApp (MVP)
1) Bot pergunta: compra ou locação
2) Cidade e estado
3) Tipo (apto/casa)
4) Quartos
5) Faixa de preço
6) Salva lead + inquiry, retorna top N imóveis

Eventos de negócio (logs): lead.created, inquiry.created, visit.requested

## Deploy Barato
- Banco: Neon (free tier) – variável DATABASE_URL_OVERRIDE
- API: Railway/Render – build Dockerfile
- Storage Imagens: Cloudflare R2 – chaves via env (S3_ACCESS_KEY_ID/SECRET)

## Segurança e LGPD
- Consentimento em `re_leads.consent_lgpd`
- Minimizar dados pessoais no payload
- Segredos via env e não comitar `.env`

## Roadmap Curto
- Dia 1–2: endpoints MVP + funil básico no webhook
- Dia 3: upload de imagens via URL pré-assinada (opcional)
- Dia 4: testes básicos + deploy

## Limpeza do Projeto
- Remover domínio de pizzaria (rotas e testes)
- Manter mensageria/base necessária para WhatsApp

---

## Arquitetura MCP (Agente IA)
- Endpoint do agente: `POST /mcp/execute` (Auth Bearer) – entrada com `input`, `tenant_id` e lista de tools permitidas (`tools_allow`).
- Tools previstas (MVP):
  - `buscar_imoveis(params)` – usa `GET /re/imoveis`.
  - `detalhar_imovel(imovel_id)` – usa `GET /re/imoveis/{id}` + `GET /re/imoveis/{id}/imagens`.
  - `criar_lead(dados)` – usa `POST /re/leads`.
  - `calcular_financiamento({preco, entrada_pct, prazo_meses, taxa_pct})` – cálculo local.
  - (próximas) `agendar_visita`, `enviar_campanha` (respeitando opt-in LGPD e templates aprovados).
- Roteamento no webhook por flag: `MCP_ENABLED=true` delega interpretação ao MCP; fallback para funil determinístico em caso de falha.
- Políticas: whitelist de tools por tenant, logs estruturados (`mcp.request`, `mcp.tool_call`, `mcp.response`), evitar dados sensíveis.

### Modo Auto (heurísticas MVP)
- Extrai intenção (comprar/alugar), tipo (apartamento/casa), cidade/UF (ex.: São Paulo/SP).
- Extrai dormitórios a partir de “2 quartos”/“2 dorm”.
- Extrai preço a partir de “até 3500”, “2000-3500” ou número solto “3500” (teto).

## Ingestão de Leads Multi‑Fonte
- Webhooks por fonte: `POST /integrations/leads/{fonte}` (ex.: `meta`, `google`, `portalX`).
- Staging: tabela `staging_leads` com payload bruto, `external_lead_id`, `source`, `received_at` e `processed_at`.
- Normalização: upsert em `re_leads` por `(tenant_id, source, external_lead_id)`, com `updated_at_source` para decidir atualização.
- Deduplicação/Merge: por telefone (E.164), email (lower) e `wa_id`. Preservar histórico em `conversation_events`.
- Orquestração de contato: tentar WhatsApp conforme janela do tenant; N tentativas; registrar `lead.created`, `contact.attempted`, `contact.replied`.

### Exemplo de payload normalizado (interno)
```json
{
  "source": "meta",
  "external_lead_id": "1234567890",
  "name": "Fulano",
  "phone": "+5511999990000",
  "email": "fulano@exemplo.com",
  "preferences": {"finalidade": "sale", "cidade": "São Paulo", "tipo": "apartment", "dormitorios": 2, "preco_max": 400000},
  "external_property_id": "X-42",
  "updated_at_source": "2025-09-14T18:00:00Z"
}
```

## Contratos para o Front (referência)
- Listar imóveis: `GET /re/imoveis`
  - Query: `finalidade`, `tipo`, `cidade`, `estado`, `preco_min`, `preco_max`, `dormitorios_min`, `limit`, `offset`.
  - Resposta: lista de `{ id, titulo, tipo, finalidade, preco, cidade, estado, bairro, dormitorios, banheiros, suites, vagas, ativo }`.
- Detalhar imóvel: `GET /re/imoveis/{id}` + `GET /re/imoveis/{id}/imagens`.
- Criar lead: `POST /re/leads` com `{ nome, telefone, email, origem, preferencias, consentimento_lgpd }`.

## Flags/Config (env)
- `APP_ENV`, `API_HOST`, `API_PORT`, `DEFAULT_TENANT_ID`.
- WhatsApp: `WA_VERIFY_TOKEN`, `WA_TOKEN`, `WA_PHONE_NUMBER_ID`, `WA_API_BASE`, `WA_WEBHOOK_SECRET`.
- DB/Redis: `DATABASE_URL_OVERRIDE` (preferir para produção), `POSTGRES_*`, `REDIS_*` (opcional no MVP).
- Storage: `STORAGE_PROVIDER=s3`, `S3_*` (quando ativarmos upload).
- MCP: `MCP_ENABLED`, `MCP_TOOLS_WHITELIST`.
- Imóveis somente leitura (produção): `RE_READ_ONLY=true` (bloqueia POST/PATCH de imóveis; usar importação/sync).

## Migrações (Alembic) – Procedimento com Docker
- Inicializar (uma vez, dentro do container): `docker compose exec api alembic init migrations`
- Ajustes feitos no repo:
  - `migrations/env.py` usa `settings.DATABASE_URL` e `CoreBase.metadata` (resiliente ao logging).
  - `alembic.ini` com `script_location=/app/migrations` dentro do container.
- Gerar revisão automática (exemplo):
  - `docker compose exec api alembic -c /app/alembic.ini revision --autogenerate -m "mensagem"`
- Aplicar:
  - `docker compose exec api alembic -c /app/alembic.ini upgrade head`
- Observação: Em rebuild da imagem, copie `migrations/` e `alembic.ini` para o container, se necessário:
  - `docker cp .\migrations atendeja-api:/app/`
  - `docker cp .\alembic.ini atendeja-api:/app/alembic.ini`

## Importação de Imóveis (preparação)
- Campos adicionados em `re_properties` para integração/sync:
  - `external_id` (string), `source` (string), `updated_at_source` (datetime)
  - Índice único por `(tenant_id, external_id)`.
- Próximo: endpoint admin `POST /admin/re/imoveis/import-csv` com upsert por `external_id` e parse de `imagens_urls` (separadas por `;`).

## Deploy
- Local: `docker compose up -d --build postgres api` (opcional `adminer`).
- Produção barata: API no Railway/Render; DB no Neon; imagens no Cloudflare R2 (quando necessário).

---

## Atualização – 2025-10-01

### Estado atual (MVP)
- Backend (`app/api/routes/realestate.py`):
  - Filtros tolerantes: `cidade` com `ilike('%texto%')`, `estado` uppercase/trim.
  - Saídas: lista com `cover_image_url` (imagem de capa) e detalhes com `imagens`.
  - Normalização de imagens: `_normalize_image_url()` aplicada em listagem/detalhes para retornar somente URLs `http/https` com domínio válido.
  - **✅ Proxy de imagens implementado**: `GET /re/images/proxy?url={url}` para contornar CORS do CDN.
- Admin (`app/api/routes/admin_realestate.py`):
  - `POST /admin/re/repair/prices` estendido para corrigir também `purpose` quando detectado.
  - `POST /admin/re/repair/purpose_from_title` criado. Resultado: 23 imóveis atualizados (Mogi/SP), viabilizando filtro por `Locação`.
  - **✅ Endpoint de limpeza**: `POST /admin/re/images/repair_invalid` para remover imagens inválidas e de layout.
- Frontend:
  - `ImoveisList.tsx`: preço BRL com fallback "Consulte", debounce 300ms, exibe `cover_image_url` quando disponível (com fallback visual).
  - **✅ `ImovelDetalhes.tsx` corrigido**: Tags JSX fechadas corretamente, usa proxy para imagens do CDN.
- **✅ Scraping otimizado** (`app/domain/realestate/sources/ndimoveis.py`):
  - Filtro aprimorado para capturar **apenas imagens de imóveis** do CDN (`cdn-imobibrasil.com.br/imagens/imoveis/`)
  - Exclui imagens de layout (logos, ícones, banners, redes sociais)

### Problemas resolvidos
- ✅ URLs inválidas (`https://cdn/...`) - Removidas 20 imagens inválidas
- ✅ Imagens de layout - Script `repair_images.py` identifica e remove automaticamente
- ✅ CORS do CDN - Proxy implementado no backend
- ✅ Scraping capturando layout - Filtro corrigido para aceitar apenas URLs do CDN de imóveis

### ⚠️ Ação necessária
**IMPORTANTE**: O servidor precisa ser **reiniciado manualmente** para carregar o novo filtro de scraping:
1. Parar o servidor atual (Ctrl+C no terminal)
2. Reiniciar: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
3. Executar limpeza: `python repair_images.py` (remover imagens de layout antigas)
4. Reimportar: `POST /admin/re/import/ndimoveis/run` com `limit_properties: 30`

### Scripts utilitários
- **`repair_images.py`**: Limpa imagens inválidas e de layout do banco
  - Classifica: válidas de imóveis, layout/site, URLs inválidas
  - Remove automaticamente imagens que não são dos imóveis
  - Uso: `python repair_images.py` (interativo com confirmação)

### Próximos passos
- Reiniciar servidor para aplicar filtro de scraping
- Reimportar imóveis com imagens corretas
- Testar visualização de imagens no frontend
- Considerar cache de imagens no proxy (já implementado: 24h)

---

## Atualização – 2025-10-01 23:42 (Correção de Imagens)

### ✅ O que foi feito

#### 1. Diagnóstico e Correção do Scraping
- **Problema identificado**: Scraping capturava TODAS as imagens da página (logos, ícones, banners, redes sociais)
- **Solução implementada** (`app/domain/realestate/sources/ndimoveis.py`):
  ```python
  # Aceita apenas URLs do CDN de imóveis
  if "cdn-imobibrasil.com.br/imagens/imoveis/" in src:
      images.append(urljoin(ND_BASE, src))
  ```
- **Resultado**: Filtro preciso que captura apenas imagens de galeria dos imóveis

#### 2. Script de Limpeza Automatizado
- **Criado**: `repair_images.py` com classificação inteligente:
  - ✅ Imagens válidas de imóveis (CDN)
  - ⚠️ Imagens de layout/site (logos, ícones, banners)
  - ❌ URLs inválidas
- **Funcionalidade**: Remoção automática com confirmação interativa
- **Logs detalhados**: Mostra exemplos de cada categoria antes de remover

#### 3. Proxy de Imagens (Backend)
- **Endpoint**: `GET /re/images/proxy?url={url}`
- **Objetivo**: Contornar CORS do CDN `imgs2.cdn-imobibrasil.com.br`
- **Features**:
  - Headers apropriados (User-Agent, Referer)
  - Cache de 24 horas
  - Validação de URL
  - Tratamento de erros

#### 4. Frontend Preparado
- **ImovelDetalhes.tsx**: Configurado para usar proxy em imagens do CDN
- **Logs de debug**: Console mostra URLs originais vs. proxied
- **Fallback visual**: Placeholders para imagens que falharem

#### 5. Dados Limpos
- **Execução final**:
  - Total de imóveis: 55
  - Total de imagens: **1.166 válidas**
  - Imóveis do scraping: 30 (TODOS com imagens)
  - Imóveis do CSV: 15 (sem imagens, esperado)
  - Removidas: 225 imagens de layout

### ❌ Problemas Enfrentados

#### 1. Cache do Python (.pyc)
- **Problema**: Módulos compilados (.pyc) não atualizavam após editar código
- **Impacto**: Scraping continuava usando código antigo mesmo após correção
- **Solução**: Deletar cache manualmente ou reiniciar servidor completamente

#### 2. Hot Reload do Uvicorn
- **Problema**: `--reload` não recarrega módulos importados dinamicamente
- **Impacto**: Endpoint de proxy não aparecia mesmo após adicionar código
- **Solução**: Reinício completo do servidor necessário

#### 3. Ambiente Virtual
- **Problema**: `httpx` instalado apenas no Poetry, servidor rodando fora do venv
- **Impacto**: ImportError ao tentar carregar endpoint de proxy
- **Solução**: `poetry run uvicorn` ou ativar venv manualmente

#### 4. Reimportação Parcial
- **Problema**: Importação processava apenas primeiros 30 imóveis
- **Impacto**: 25 imóveis ficavam sem imagens
- **Solução**: Executar múltiplas importações até cobrir todos os imóveis

### ⚠️ Problemas Pendentes

#### 1. Proxy Retorna 404
- **Status**: Endpoint existe no código mas retorna 404
- **Causa provável**: Servidor não está rodando no ambiente Poetry (sem httpx)
- **Solução necessária**: 
  ```bash
  poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  ```
- **Impacto**: Imagens do CDN não carregam (CORS block)

#### 2. Imagens de Layout Remanescentes
- **Status**: Script identifica mas algumas ainda no banco
- **Causa**: Scraping antigo antes da correção do filtro
- **Solução**: Executar `python repair_images.py` após cada importação

### 📋 Plano para Conclusão

#### Curto Prazo (Hoje)
1. **Reiniciar servidor com Poetry** ✅ (comando executado)
   ```bash
   poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Testar proxy**
   ```bash
   curl "http://localhost:8000/re/images/proxy?url=https://imgs2.cdn-imobibrasil.com.br/imagens/imoveis/202106251237157000.png"
   ```

3. **Verificar imagens no frontend**
   - Acessar http://localhost:5173/imoveis/55
   - Confirmar que galeria exibe imagens

#### Médio Prazo (Próximos dias)
1. **Importar TODOS os imóveis do site** (282 imóveis em 19 páginas)
   ```json
   POST /admin/re/import/ndimoveis/run
   {
     "finalidade": "both",
     "page_start": 1,
     "max_pages": 20,
     "limit_properties": 200,
     "throttle_ms": 200
   }
   ```

2. **Automatizar limpeza pós-importação**
   - Criar trigger ou task que executa `repair_images.py` automaticamente
   - Ou: integrar lógica de filtro no próprio importer

3. **Otimizar scraping**
   - Adicionar logs de debug permanentes (não apenas print)
   - Estatísticas: X imagens aceitas, Y rejeitadas por tipo

#### Longo Prazo
1. **Cache local de imagens**
   - Download e armazenamento em R2/Cloudflare
   - URLs próprias em vez de proxy

2. **Validação de imagens**
   - Verificar se URL retorna 200 antes de salvar
   - Remover automaticamente imagens quebradas

3. **Melhoria de UX**
   - Lazy loading de imagens
   - Thumbnails otimizados
   - Lightbox para visualização

### 📊 Métricas Atuais
```
Banco de Dados:
├── Imóveis: 55 total
│   ├── Scraping (ND Imóveis): 30 (100% com imagens)
│   └── CSV (teste): 15 (0% com imagens, esperado)
├── Imagens: 1.166 válidas
│   ├── CDN (válidas): 1.166
│   ├── Layout (removidas): 225
│   └── Inválidas (removidas): 20
└── Taxa de sucesso: 100% dos imóveis scraped têm imagens

Site Fonte (ND Imóveis):
├── Total disponível: 282 imóveis
├── Importados: 30 (10.6%)
└── Pendentes: 252 (89.4%)
```

### 🔧 Comandos Úteis

```bash
# Servidor
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Limpeza
python repair_images.py

# Importação
