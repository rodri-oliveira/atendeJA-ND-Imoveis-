# Deploy Runbook (MVP/SaaS)

Este runbook é o passo a passo operacional para subir o SaaS em produção (Render + Neon + Upstash), rodar migrations e validar com smoke test.

## 1) Pré-requisitos

- Repositório conectado ao Render (deploy automático por branch/tag).
- PostgreSQL no Neon (DATABASE_URL do Neon disponível).
- Redis no Upstash (REDIS_URL disponível).
- WhatsApp Business API configurado (pelo menos para 1 tenant).

## 2) Variáveis de ambiente (Render)

### Obrigatórias (backend)

- `APP_ENV=prod`
- `AUTH_JWT_SECRET=<string forte e estável>`
- `SUPER_ADMIN_API_KEY=<string forte>`
- `DATABASE_URL_OVERRIDE=<DATABASE_URL do Neon>`
- `REDIS_HOST` / `REDIS_PORT` / `REDIS_DB` **ou** configurar `REDIS_URL` (preferível)
- WhatsApp:
  - `WA_PROVIDER=meta`
  - `WA_TOKEN=<token do Meta>`
  - `WA_VERIFY_TOKEN=<string criada por você>`
  - `WA_WEBHOOK_SECRET=<opcional>`

### Recomendadas

- `AUTH_SEED_ADMIN_EMAIL=admin@example.com`
- `AUTH_SEED_ADMIN_PASSWORD=<senha forte>`

### LLM (opcional)

- `OPENAI_API_KEY=<chave>` (se não setar, a IA fica “off” sem quebrar)
- `OPENAI_MODEL=gpt-4o-mini`
- `OPENAI_TIMEOUT_SECONDS=20`
- Guardrails:
  - `OPENAI_MAX_CALLS_PER_TENANT_PER_DAY=500`
  - `OPENAI_MAX_CALLS_PER_SENDER_PER_MINUTE=6`

## 3) Subir serviços (Render)

### Backend (Web Service)

- Start command típico:
  - `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Frontend (Static Site)

- Build: `npm ci && npm run build`
- Publish directory: `frontend/ui/dist`

## 4) Migrations (Alembic) – procedimento

> Objetivo: garantir que o schema do Neon está em `head`.

1. Faça deploy do backend no Render.
2. Abra o **Render Shell** do serviço do backend.
3. Rode:

```bash
alembic upgrade head
```

4. Se falhar:
- Verifique `DATABASE_URL_OVERRIDE` (Neon)
- Verifique conectividade (egress) do Render
- Rode `alembic current` e `alembic history` para diagnosticar

## 5) Smoke test (produção)

### 5.1 Health

- `GET /health/liveness` (200)
- `GET /health/readiness` (200)

### 5.2 Login admin

- `POST /auth/login` com `admin@example.com` e a senha do seed.
- Guarde o JWT.

### 5.3 Admin flows (scoped por tenant do JWT)

- `GET /admin/chatbot-domain`
- `GET /admin/chatbot-flows?domain=real_estate`
- `GET /admin/chatbot-flows/published?domain=real_estate`

### 5.4 Super-admin onboarding (novo cliente)

- Com header `X-Super-Admin-Key: <SUPER_ADMIN_API_KEY>`:
  - `POST /super/tenants`
  - `POST /super/tenants/{tenant_id}/whatsapp-accounts` (phone_number_id → tenant)
  - (opcional) `POST /super/tenants/{tenant_id}/invite-admin`

### 5.5 Webhook WhatsApp

- Configure webhook no Meta apontando para:
  - `GET /webhook/verify` (challenge)
  - `POST /webhook` (mensagens)

- Validação:
  - ao chegar uma mensagem com `phone_number_id`, o sistema deve:
    - resolver tenant via `whatsapp_accounts`
    - carregar flow publicado do tenant/domínio
    - responder sem erro

## 6) Rollback (estratégia simples MVP)

- Código: redeploy da release anterior no Render.
- Banco:
  - Evitar `downgrade` em produção.
  - Se uma migration quebrar, a prática recomendada é criar uma migration “fix forward”.

## 7) Troubleshooting rápido

- **401 `invalid_token` no admin**:
  - Token antigo após troca de `AUTH_JWT_SECRET`.
  - Solução: manter `AUTH_JWT_SECRET` estável + relogar.

- **404 `tenant_not_mapped_for_phone_number_id` no webhook**:
  - Falta registro em `whatsapp_accounts`.
  - Solução: criar WhatsAppAccount no `/super/tenants`.

- **500 em endpoints admin**:
  - Verificar logs com `correlation_id`.
  - Validar migrations no Neon (`alembic upgrade head`).

## 8) Backup e operação

- Neon: habilitar/confirmar backups automáticos.
- Render: manter logs e alertas (erros 5xx, latência, quedas).
- Upstash: observar limites do plano (comandos/dia) e ajustar guardrails conforme uso.
