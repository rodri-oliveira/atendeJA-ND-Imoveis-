---
description: Direção multi-domínio + onboarding por URL (AtendeJá)
---

# Objetivo

Evoluir o AtendeJá de um SaaS de nicho (imobiliário) para uma **plataforma multi-domínio** (ex.: imobiliário, concessionária etc.) **reutilizando** a infraestrutura atual do chatbot (guardrails, segurança, estado, observabilidade), evitando regressão.

# O que foi feito (Resumo do Progresso Recente)

- **Super Admin & Multi-Tenant UX:**
  - Habilitado modo **Super Admin** com chave de API (`SUPER_ADMIN_API_KEY`) para visão global de todos os tenants.
  - Criada a página `/super/tenants` para listar e gerenciar clientes.
  - Implementado botão **"Entrar neste tenant"**, permitindo ao Super Admin navegar no contexto de diferentes clientes sem precisar deslogar. A troca de tenant agora é fluida e reflete em toda a aplicação.

- **Página de Leads (Kanban):**
  - O card do lead no Kanban agora exibe um **resumo dinâmico** (`lead_summary`) com as principais informações capturadas pelo chatbot, agilizando a triagem.
  - Corrigido bug crítico onde a lista de leads **não atualizava** ao trocar de tenant. A solução usou um Contexto React global para o `tenantId`, tornando a UI reativa.

- **Infraestrutura e UI Dinâmica:**
  - Criado endpoint `GET /api/ui/domain` para que o frontend possa adaptar a navegação (ex: menu lateral) ao domínio do tenant (`real_estate`, `car_dealer`, etc.).
  - Resolvido problema de proxy no Vite que causava 404 em ambiente de desenvolvimento.

# Fonte de verdade (o que já existe no código)

- **Multi-tenant (HTTP/Admin)**
  - `X-Tenant-Id` resolve tenant em rotas HTTP.
  - Admin usa `RequestContext` via `require_admin_request_context`.
- **Multi-tenant (WhatsApp)**
  - Webhook resolve `tenant` via `whatsapp_accounts.phone_number_id`.
- **Domínio do chatbot por tenant**
  - `tenants.settings_json.chatbot_domain` (default `real_estate`).
- **Flow as Data**
  - tabela `re_chatbot_flows` (modelo `ChatbotFlow`) com `tenant_id + domain + name` unique.
  - published flow selecionado por `tenant_id + domain`.
- **Templates de flow**
  - `app/domain/chatbot/flow_templates.py` (ex.: `real_estate/default`, `car_dealer/default`).
- **Handler por domínio (fallback/compat)**
  - `app/domain/chatbot/handler_factory.py` (ex.: `real_estate`, `car_dealer`).
- **Catálogo genérico + ingestão de veículos**
  - `catalog_item_types`, `catalog_items`, `catalog_media`, `catalog_external_references`.
  - `VehicleIngestionService` faz upsert idempotente por (`tenant_id`, `source`, `external_key`).

# Onboarding “inteligente” por URL (novo cliente)

## Objetivo

Um admin (super-admin) informa uma URL do cliente e o sistema:

- cria tenant
- configura domínio
- cria/associa WhatsAppAccount (quando aplicável)
- executa discovery/ingestion
- aplica template de flow adequado
- publica flow
- deixa pronto para o webhook atender sem deploy

## Fluxo proposto (V1)

- **Passo 1**: Criar tenant
- **Passo 2**: Definir `chatbot_domain`
- **Passo 3**: Aplicar template do flow (`/admin/chatbot-templates/apply`)
- **Passo 4**: Publicar flow (se template não publicar)
- **Passo 5**: Ingestão catálogo por URL (ex.: veículos)
- **Passo 6**: Validar via preview do flow + listar catálogo

# Próximos passos (Plano Futuro)

1.  **Evoluir Catálogo para ser genérico e multi-domínio**.
    -   **Objetivo:** Permitir que a plataforma suporte diferentes nichos (veículos, imóveis, etc.) de forma escalável.
    -   **Ações:**
        -   Tornar `CatalogItemType` e `CatalogItem` mais flexíveis, baseados em um schema JSON (`FieldDefinition`).
        -   Adaptar a UI de `CatalogAdmin` para renderizar formulários e listas dinamicamente a partir do schema.
        -   Criar pipelines de ingestão plugáveis por tipo de item/domínio.

2.  **Consolidar UI Admin unificada**.
    -   **Objetivo:** Evitar rotas fixas por nicho (ex: `/imoveis`) e ter uma navegação que se adapta ao contexto.
    -   **Ações:**
        -   A UI deve se basear no `tenantId` e `chatbot_domain` para montar menus e rotas.

3.  **Finalizar Onboarding por URL**.
    -   **Objetivo:** Automatizar a criação de um novo cliente de ponta a ponta.
    -   **Ações:**
        -   Integrar os passos de discovery, ingestão, aplicação de template e publicação em um único fluxo coeso na UI do Super Admin.
