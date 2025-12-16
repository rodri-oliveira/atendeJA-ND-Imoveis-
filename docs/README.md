# Docs – Norte do Projeto (AtendeJá ND Imóveis)

Este diretório é a referência única do projeto. Sempre que houver dúvida de “o que vamos fazer” e “como vamos operar/deployar”, consulte este arquivo primeiro.

## 1) Objetivo do produto
- Chatbot imobiliário para atendimento via WhatsApp.
- Listagem/gestão de imóveis via painel web.
- Consulta de imóveis pelo chat (MCP) usando a base no PostgreSQL.

## 2) Objetivos imediatos (para deploy)
- Garantir que API/Worker usam PostgreSQL.
- Restaurar base completa de imóveis via import/scraping ND Imóveis.
- Subir backend + frontend + integrações com configuração segura (segredos fora do Git).

## 3) Stack e componentes
- Backend: FastAPI (Python 3.11)
- Banco: PostgreSQL
- Cache/estado: Redis
- Worker: Celery
- Frontend: React (admin)
- Chat/orquestração: MCP (`/api/v1/mcp/execute`)

## 4) Decisões de arquitetura (referência)
### 4.1 Banco de dados (PostgreSQL)
- Produção: PostgreSQL (preferencialmente gerenciado).
- Desenvolvimento: PostgreSQL pode rodar via Docker Compose.

Motivo: banco é componente stateful e exige backup/restore/monitoramento/upgrade. Em produção, serviço gerenciado reduz risco operacional e risco de perda de dados.

### 4.2 Configuração de banco no backend
O backend monta `settings.DATABASE_URL` a partir de variáveis no `.env` (ver `app/core/config.py`):
- Preferência: `DATABASE_URL_OVERRIDE` (quando definido)
- Caso vazio: usa `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

Recomendação por ambiente:
- DEV/local: manter `DATABASE_URL_OVERRIDE=` vazio e preencher `POSTGRES_*`
- PROD: usar `DATABASE_URL_OVERRIDE` com a URL do provedor

### 4.3 Segurança mínima para deploy
- `AUTH_JWT_SECRET` deve ser forte em produção.
- `MCP_API_TOKEN` deve ser definido em produção.
- `AUTH_SEED_ADMIN_*`:
  - DEV: pode existir
  - PROD: evitar senha fraca; ideal seed controlado e troca imediata

## 5) Restaurar a base de imóveis (prioridade)
A base deve existir no PostgreSQL para o frontend e o chat retornarem imóveis.

Fontes previstas:
- Import/scraping ND Imóveis (principal)
- Import CSV (fallback)

Operação esperada:
- Rodar import/scraping via endpoints admin:
  - `import/ndimoveis/check|run|enqueue|repair_*`

## 6) Como rodar localmente (atalhos)
- Docker (Postgres + Redis): ver `MVP-SETUP.md`
- Operação/infra de produção (custos e provedores): ver `INFRAESTRUTURA-CLIENTE.md`

## 7) Links importantes (documentos existentes)
- `MVP-SETUP.md` – como subir o projeto localmente
- `INFRAESTRUTURA-CLIENTE.md` – opções e guia de infra de produção
- `REAL_ESTATE_PLAN.md` – plano do domínio imobiliário, endpoints e import ND
- `CHAT-PLAN.md` – plano e decisões do chat/MCP
