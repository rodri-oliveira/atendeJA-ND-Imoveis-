# Plano de Evolução para Arquitetura Multi-Domínio

Este documento descreve o plano estratégico para evoluir a arquitetura do AtendeJá de um SaaS de nicho (imobiliário) para uma plataforma de chatbot multi-domínio (imobiliário, automotivo, etc.), de forma segura e gradual, sem reescrever o código do zero e preservando a funcionalidade atual.

A abordagem se baseia em dois conceitos principais:
1.  **Flow as Data:** A lógica da conversa (o fluxo de perguntas e respostas) deixa de ser fixa no código e passa a ser uma configuração (JSON) armazenada no banco de dados, associada a cada tenant.
2.  **Catálogo Genérico:** A estrutura de dados para os itens de catálogo (imóveis, carros) é generalizada para suportar diferentes tipos de atributos.

---

## Estado atual do Banco (para evitar redundância)

Este plano assume que algumas migrações já podem ter sido aplicadas no banco.

1.  **Flow as Data (tabela de fluxos):**
    *   A tabela utilizada pelo código é `re_chatbot_flows` (modelo `ChatbotFlow`).
    *   Existe um índice único por `tenant_id + name`.
    *   Implicação: seed deve ser **idempotente** (upsert ou delete+insert controlado), para não duplicar nem quebrar por unique constraint.

2.  **Catálogo genérico:**
    *   O catálogo genérico usa `catalog_items` e `catalog_item_images`.
    *   Implicação: scripts de migração devem ser idempotentes (não duplicar itens/imagens) e devem respeitar `tenant_id`.

3.  **Legado imobiliário:**
    *   Pode existir `re_properties` em paralelo durante a migração.
    *   Regra: não remover legado até a migração completa e sem referências em rotas/services ativos.

---

## Guardrails (Regras de Execução para não quebrar o produto)

1.  **Ordem é obrigatória:** não executar Fase 2 (catálogo genérico) “por cima” da Fase 1 sem uma camada explícita de compatibilidade. A remoção do legado (ex: `Property`) só ocorre na última etapa.
2.  **Boot sempre verde:** a API deve subir mesmo durante migração. Qualquer módulo/rota/admin que dependa do legado precisa ser isolado (compatibilidade ou import-safe) até ser migrado.
3.  **Tenant default sempre resolvível:** o sistema deve sempre conseguir resolver um `tenant_id` numérico para carregar fluxo.
    *   Em `.env`, `DEFAULT_TENANT_ID` deve ser **numérico** (ex: `1`, `2`).
    *   O tenant default deve possuir um fluxo seed (ou um fallback controlado).
4.  **Fluxo seed por tenant:** sem seed, o MCP deve falhar com diagnóstico claro (e não com erro genérico/confuso).
5.  **Validação por estágio:** cada etapa deve validar contexto. Exemplos:
    *   `awaiting_name`: rejeitar saudações (`oi`, `olá`) e pedir novamente.
    *   `awaiting_lgpd_consent`: aceitar somente confirmações explícitas (não depender de LLM).
6.  **LLM não decide booleanos críticos:** LGPD, comandos globais e transições sensíveis devem ser determinísticos (regex/palavras-chave). LLM pode ajudar em extração de entidades (cidade, preço, intenção) com sanitização.
7.  **Tenant propagado ponta-a-ponta (sem hardcode):** qualquer escrita em banco que crie/atualize registros “do tenant” deve receber e persistir `tenant_id` de forma explícita (ex.: vindo do MCP request / headers / token / state). É proibido “fixar `tenant_id=1`” em services.
8.  **Estado/Redis não pode mascarar bug de tenant:** ao alternar tenant em DEV, limpar estado do `sender_id` antes de testar (ou usar sender_id diferente por tenant). Caso contrário, o fluxo pode continuar em estágio antigo e gerar diagnósticos falsos.
9.  **Migrations resilientes a reset:** após `git reset`/rebase, validar Alembic (revisions presentes) antes de rodar o app. Evitar apagar arquivos de migration que já foram aplicados; se necessário, criar migração “dummy” com revisão correta e documentar o procedimento de `stamp`.
10. **Observabilidade mínima:** logs devem sempre incluir `tenant_id`, `sender_id` e `stage` para rastrear inconsistências (ex.: lead “some” porque foi salvo no tenant errado).

---

## Checklist Operacional (antes de subir/alterar arquitetura)

1.  **Configuração de tenant:**
    *   `DEFAULT_TENANT_ID` numérico e existente no banco.
    *   Adapter WA (DEV): `MCP_TENANT_ID` alinhado ao tenant que você está testando.
2.  **Seed do fluxo:**
    *   Garantir 1+ fluxo em `re_chatbot_flows` para o tenant alvo.
    *   Seed idempotente (upsert por `tenant_id + name`).
3.  **Compatibilidade de imports:**
    *   Se modelos legados existirem, nenhuma rota “core” deve quebrar boot.
    *   Rotas/admin dependentes do legado devem ser import-safe (isoladas) até migração completa.
4.  **Tenant em writes críticos:**
    *   Leads, flows, catalog_items e imagens sempre persistidos com `tenant_id` explícito.
    *   Antes de testar, validar no banco (query por `tenant_id`) se a gravação foi no tenant correto.
5.  **Smoke tests (E2E mínimo):**
    *   Novo contato: `oi` → mensagem inicial (sem avançar indevidamente).
    *   LGPD: somente confirmações explícitas avançam.
    *   Funil imobiliário: buscar → mostrar → feedback (`não encontrei imóvel` salva lead com status esperado no tenant correto).
6.  **Migrations:**
    *   `alembic current` e `alembic history` sem erro.
    *   Se houve reset/rebase, confirmar presença dos arquivos de revision aplicados.

---

## Fonte de verdade do Tenant (contrato único)

Para evitar inconsistências (principalmente em DEV) e impedir que dados “sumam” por estarem sendo salvos/consultados no tenant errado, definir um contrato único de resolução de `tenant_id`.

**Prioridade recomendada para resolver `tenant_id`:**
1.  **Header `X-Tenant-Id`** (admin/web/requests de frontend).
2.  **JWT** (`tenant_id` no token do usuário logado, quando aplicável).
3.  **Body do MCP** (`tenant_id` no request do adapter, ex.: `MCP_TENANT_ID`).
4.  **Fallback `DEFAULT_TENANT_ID`** (somente em DEV/test).

**Regra:** toda rota/service que interage com dados multi-tenant deve usar a mesma função/helper de resolução (evitar “cada rota decide de um jeito”).

---

## Checklist de Pull Request (anti-regressão multi-tenant)

Antes de aprovar PRs que mexem em chat/lead/catálogo/flows, validar:

1.  **Sem hardcode de tenant:**
    *   Não existe `tenant_id=1` (ou qualquer literal) em services/repos.
    *   Escritas (create/update) recebem `tenant_id` explicitamente do contexto.
2.  **Queries filtradas por tenant:**
    *   Toda consulta em tabelas multi-tenant filtra por `tenant_id` (principalmente em `Lead`, `ChatbotFlow`, `CatalogItem`).
3.  **Upsert seguro por tenant:**
    *   Upsert por telefone/email precisa considerar `tenant_id` (mesmo telefone pode existir em tenants distintos).
4.  **Boot verde com compatibilidade:**
    *   Imports de legado não quebram boot (rotas/admin isoladas/import-safe).
5.  **Logs com contexto:**
    *   Logs principais incluem `tenant_id`, `sender_id`, `stage`.
6.  **Smoke tests (manual ou automatizado):**
    *   Conversa nova: `oi` → LGPD.
    *   LGPD avança apenas com confirmação explícita.
    *   `não encontrei imóvel` salva lead com status esperado no tenant correto.

---

## Decisão Arquitetural (V1) — Gestão de Flows

Para o V1 do painel administrativo e do motor “Flow as Data”, a decisão é priorizar simplicidade operacional e segurança.

1.  **1 flow publicado por tenant + domínio:**
    *   Para cada par (`tenant_id`, `domain`) existe exatamente 1 flow em produção (publicado) ativo.
    *   Evita ambiguidade e reduz risco de selecionar o flow errado em runtime.

2.  **Draft separado do publicado:**
    *   O operador edita um rascunho (draft) sem afetar o flow publicado.
    *   Publicação deve ser uma troca atômica (após validar e testar).

3.  **Versionamento mínimo obrigatório:**
    *   Cada publicação deve registrar metadados (ex.: `published_at`, `published_by`, `published_version`).
    *   Manter histórico das últimas versões publicadas para rollback rápido.

4.  **Duplicação permitida, mas controlada:**
    *   Permitir duplicar um flow publicado para gerar um novo draft.
    *   Regra: apenas 1 publicado por (`tenant_id`, `domain`); os demais ficam como drafts/arquivados.

5.  **Workflow padrão do painel:**
    *   Validar → Testar (simulação) → Publicar → (se necessário) Reverter para versão anterior.

---

## Playbook Anti-Regressão (Git, Migrations, Rollback)

O objetivo desta seção é evitar repetir problemas operacionais comuns durante refactors (boot quebrando, Alembic inconsistente, dados “sumindo” por tenant errado, etc.).

1.  **Git: evitar reset destrutivo sem estratégia**
    *   Preferir `git revert` para desfazer mudanças já publicadas, em vez de reescrever histórico.
    *   Se precisar reescrever histórico (ex.: `reset --hard`):
        *   Assumir que migrations podem ficar inconsistentes.
        *   Documentar o commit alvo e validar `git reflog` para possível recuperação.

2.  **Migrations: regra de ouro**
    *   Não apagar migration que já foi aplicada em algum ambiente.
    *   Após `reset`/rebase, antes de rodar o app:
        *   Validar que os arquivos de revision existem no repo.
        *   Validar Alembic (ex.: `alembic history` e `alembic current`).
    *   Se uma revision aplicada “sumiu” do repo:
        *   Criar migration “dummy” com o `revision` esperado para restaurar a cadeia.
        *   Executar `alembic stamp` apenas com entendimento claro do estado do banco.

3.  **Rollback do chat (Flow as Data)**
    *   Publicação deve ser reversível sem deploy:
        *   Manter histórico de versões publicadas.
        *   Permitir “reverter para versão anterior” no painel.
    *   Regra: publicar apenas após validação do schema e smoke test de simulação.

4.  **Diagnóstico rápido (quando “parou de funcionar”)**
    *   Confirmar `tenant_id` resolvido (logs) e `DEFAULT_TENANT_ID` numérico.
    *   Confirmar seed do flow para o tenant.
    *   Confirmar que o estado do `sender_id` no Redis não está “preso” em outro estágio.

---

## Matriz de Testes Obrigatórios (por fase)

1.  **Fase 1 (Flow as Data):**
    *   Boot da API sobe sem erro mesmo com legado presente.
    *   Conversa nova:
        *   `oi` → mensagem inicial.
        *   LGPD só avança com confirmação explícita.
        *   fluxo completo até busca e apresentação.
    *   Troca de tenant (DEV): validar que `tenant_id` entra no state e no log.

2.  **Fase 2 (Catálogo Genérico):**
    *   Busca/detalhe por `CatalogItem` retorna dados esperados por tenant.
    *   Imagens por `CatalogItemImage` retornam na ordem esperada.
    *   Migração idempotente (rodar 2x não duplica).

3.  **Fase 3 (Novo domínio):**
    *   Tenant automotive com flow seedado e catálogo carregado.
    *   UI/admin adapta sem ifs espalhados (por `domain`).

---

## Fase 1: Implementar "Flow as Data" (Domínio Imobiliário)

O objetivo desta fase é refatorar o motor de conversa para que ele leia o fluxo de um modelo de dados, em vez de seguir uma lógica "hardcoded". A funcionalidade para o cliente atual (ND Imóveis) permanecerá idêntica.

### Passos Técnicos:

1.  **Modelagem do Banco de Dados:**
    *   Criar a tabela `re_chatbot_flows` para armazenar as definições dos fluxos de conversa.
        *   `id`: Chave primária.
        *   `tenant_id`: Chave estrangeira para a tabela `tenants` (permite fluxos customizados por cliente).
        *   `domain`: Um campo de texto para categorizar o fluxo (ex: `real_estate`, `automotive`). Inicialmente, todos serão `real_estate`.
        *   `name`: Nome do fluxo (ex: "Fluxo Padrão de Venda Imobiliária").
        *   `flow_definition`: Um campo `JSON` que conterá a estrutura completa do chat.

2.  **Definição do Fluxo em JSON:**
    *   Mapear a lógica atual de `app/domain/realestate/conversation_handlers.py` para uma estrutura JSON. Este JSON descreverá cada passo, as mensagens a serem enviadas, as funções de validação a serem chamadas e as transições para os próximos passos.
    *   **Exemplo de Estrutura JSON:**
        ```json
        {
          "initial_step": "greeting",
          "steps": {
            "greeting": {
              "message_template": "GREETING_MESSAGE",
              "next_step": "purpose"
            },
            "purpose": {
              "message_template": "ASK_PURPOSE",
              "detection_handler": "detect_purpose",
              "next_steps": {
                "sale": "property_type",
                "rent": "property_type",
                "fallback": "purpose_fallback"
              }
            },
            "property_type": {
              "message_template": "ASK_PROPERTY_TYPE",
              "detection_handler": "detect_property_type",
              "next_step": "city"
            }
          }
        }
        ```

3.  **Refatoração do Motor de Conversa (`ConversationEngine`):**
    *   Modificar o motor para que, ao iniciar uma conversa, ele carregue o `flow_definition` do tenant correspondente.
    *   Em vez de chamar funções de handler diretamente, o motor irá interpretar o JSON do passo atual para:
        *   Enviar a mensagem correta (usando `message_template`).
        *   Chamar a função de detecção/validação apropriada (usando `detection_handler`).
        *   Determinar o próximo passo com base no resultado.
    *   As funções em `detection_utils.py`, `validation_utils.py` e `message_formatters.py` serão mantidas e reutilizadas, sendo apenas chamadas dinamicamente pelo motor.

4.  **Seed e Configuração Inicial (Obrigatório para testes):**
    *   Garantir ao menos 1 registro em `re_chatbot_flows` para o tenant default.
    *   Definir no `.env` um `DEFAULT_TENANT_ID` numérico.
    *   Testes mínimos (antes de seguir para Fase 2):
        *   Enviar "oi" e verificar que retorna a mensagem de boas-vindas/LGPD.
        *   Enviar "sim" e verificar que avança para coleta de nome.
        *   Persistência de estado (Redis) deve manter `stage` corretamente.
        *   Validar que logs incluem `tenant_id` e que o `state` guarda `tenant_id` resolvido (evita salvar dados no tenant errado).

**Critério de pronto (Fase 1):**
*   O chat completo do imobiliário roda end-to-end pelo JSON (sem depender de `ConversationHandler` hardcoded).
*   O boot do FastAPI não depende de modelos legados removidos.
*   `DEFAULT_TENANT_ID` numérico + fluxo seed presente.

**Resultado da Fase 1:** O sistema funcionará como antes, mas a arquitetura estará pronta para suportar múltiplos fluxos de conversa sem alterações no código do motor.

---

## Fase 2: Generalizar o Catálogo de Produtos

O objetivo é desacoplar o sistema da estrutura fixa de "imóveis" para suportar qualquer tipo de produto (carros, serviços, etc.).

### Passos Técnicos:

1.  **Modelagem do Banco de Dados:**
    *   Criar uma nova tabela `catalog_items` para substituir `re_properties`.
        *   `id`: Chave primária.
        *   `tenant_id`: Chave estrangeira.
        *   `domain`: `real_estate`, `automotive`, etc.
        *   `name`: Nome do item (ex: "Apartamento no Centro", "Toyota Corolla 2023").
        *   `description`: Descrição.
        *   `images`: Campo `JSON` para a lista de URLs de imagens.
        *   `attributes`: Campo `JSON` para armazenar os dados específicos do domínio (ex: `{"bedrooms": 3, "area": 120}` ou `{"brand": "Toyota", "model": "Corolla", "year": 2023}`).

2.  **Migração de Dados:**
    *   Criar um script para migrar todos os registros da tabela `re_properties` para a nova `catalog_items`, mapeando as colunas existentes para o campo `attributes`.

3.  **Adaptação do Código:**
    *   Refatorar todas as partes do backend e frontend que atualmente interagem com `re_properties` para que passem a usar `catalog_items`.
    *   A UI de exibição de detalhes e os filtros precisarão ser adaptados para ler e renderizar os atributos dinamicamente a partir do campo `JSON`.

4.  **Estratégia de Compatibilidade (Obrigatória durante a migração):**
    *   Enquanto houver rotas/services/admin que ainda dependam do legado, manter uma camada de compatibilidade:
        *   Mappers de `CatalogItem` -> “view model” de imóvel.
        *   Funções/aliases compatíveis (quando necessário).
    *   Não remover `Property`/`PropertyImage` até:
        *   `grep` no repositório sem referências em rotas/services ativos.
        *   API sobe e endpoints críticos não importam legado.
    *   Se houver dependência temporária, preferir:
        *   Adapters/mappers (`CatalogItem` → view model de imóvel).
        *   Imports tolerantes a falha para rotas administrativas (não bloquear boot).

**Critério de pronto (Fase 2):**
*   Leitura/busca/detalhe do catálogo do domínio imobiliário usando `CatalogItem`.
*   Imagens usando `CatalogItemImage`.
*   Migração completa e verificada por tenant.

**Resultado da Fase 2:** O sistema será capaz de gerenciar diferentes tipos de produtos, cada um com seu próprio conjunto de atributos, sem estar preso ao esquema imobiliário.

---

## Fase 3: Introduzir o Domínio "Automotive"

Com a fundação das fases 1 e 2 pronta, adicionar um novo domínio de negócio se torna uma tarefa de configuração, não de codificação.

### Passos Técnicos:

1.  **Adicionar o Conceito de Domínio ao Tenant:**
    *   Adicionar uma coluna `domain` na tabela `tenants` para definir o tipo de negócio principal de cada cliente.

2.  **Criar o Template de Fluxo Automotivo:**
    *   Criar um novo registro na tabela `chatbot_flows` com `domain = 'automotive'`.
    *   Definir o `flow_definition` em JSON para a conversa de uma concessionária (perguntar sobre marca, modelo, ano, troca, etc.).

3.  **Ajustes na Interface de Administração:**
    *   A UI do admin (painel de leads, catálogo) deve se adaptar com base no `domain` do tenant logado.
    *   Se o `domain` for `automotive`, a UI de cadastro de itens de catálogo deve exibir campos para "Marca", "Modelo", "Ano", em vez de "Quartos", "Banheiros", "Área".

**Critério de pronto (Fase 3):**
*   Novo fluxo automotivo seedado por tenant.
*   Catálogo genérico suporta `automotive` sem mudanças de schema.
*   Admin/UI se adapta por `domain` sem ifs espalhados.

**Resultado Final:** O AtendeJá se tornará uma plataforma multi-domínio, capaz de atender diferentes verticais de negócio com fluxos de conversa e catálogos de produtos específicos, tudo sobre uma única base de código unificada e escalável.