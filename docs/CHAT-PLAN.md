 # Plano e Resumo do Chat WhatsApp – ND Imóveis (MVP)
 
 ## Resumo do que foi feito
 - **[rotas MCP]** Alinhado o endpoint público para `POST /api/v1/mcp/execute`.
   - `app/main.py`: `app.include_router(mcp_router, prefix="/api/v1/mcp", tags=["mcp"])`.
   - `app/api/routes/mcp.py`: `@router.post("/execute")`.
 - **[consumidores corrigidos]**
   - `tests/test_mcp_leads.py`: atualizado para `"/api/v1/mcp/execute"` e adicionado `sender_id` (obrigatório em `MCPRequest`).
   - `adapter-wa/index.js` e `adapter-wa/README.md`: `MCP_URL=http://localhost:8000/api/v1/mcp/execute`.
   - Ajuste no adapter (auto-teste): bypass de whitelist quando `msg.from` está na whitelist.
 - **[dependências e testes]** venv `.venv` criada; libs instaladas conforme `pyproject.toml`/`requirements.txt`; `pytest -q` verde.
 - **[infra local produção-like]** Docker Desktop/WSL restabelecidos; `redis` iniciado via `docker compose up -d redis`.
 
 ## Problemas enfrentados (com evidência) e soluções
 - **[404 Not Found no MCP]**
   - Causa: consumidores chamavam `"/mcp/execute"` enquanto o servidor expõe `"/api/v1/mcp/execute"`.
   - Solução: atualizar caminhos nos testes e adapter para incluir o prefixo `/api/v1/mcp`.
 - **[422 Unprocessable Entity]**
   - Causa: campo obrigatório `sender_id` ausente no body do MCP.
   - Solução: incluir `sender_id` nos testes e nas chamadas manuais.
 - **[500 internal_error no MCP (modo auto)]**
   - Causa (confirmada no código): `ConversationStateService` usa Redis diretamente (`get/setex/delete`) sem fallback; ausência do Redis gera exceção e o middleware global (`app/main.py`) retorna 500 com `{"error":{"code":"internal_error"...}}`.
   - Evidências: `app/api/deps.py` injeta `ConversationStateService(redis_client=...)` e `app/services/conversation_state.py` faz chamadas diretas ao Redis.
   - Solução: subir Redis com `docker compose up -d redis` e testar novamente (resolvido).
 - **[PowerShell vs curl]**
   - Causa: no PowerShell, `curl` é alias de `Invoke-WebRequest` (não aceita `-X/-H/-d` como no curl nativo).
   - Solução: usar `Invoke-RestMethod` ou `curl.exe` para testar o MCP.
 - **[Adapter WA – tipos e whitelist]**
   - Comportamento: ignora `type: image/ptt`; processa apenas `type: chat` (texto). Whitelist ativa em `WA_ONLY_CONTACTS`.
   - Ajuste: bypass para `fromMe` quando `msg.from` está na whitelist (facilita auto-teste).
 
 ## Prevenções para não ocorrer novamente
 - **[contrato de API consistente]** Centralizar o base path (`/api/v1`) em config compartilhada e adicionar teste de integração que valide `POST /api/v1/mcp/execute` com `sender_id`.
 - **[observabilidade de Redis]**
   - Adicionar verificação de readiness do Redis no startup (ex.: `ping`) com log claro.
   - Tratar indisponibilidade com erro 503 explicitando causa (ao invés de 500 genérico), mantendo paridade com produção.
 - **[DX no Windows]** Documentar no `README-PT.md` exemplos com `Invoke-RestMethod` e `curl.exe`.
 - **[scripts de dev]** Criar alvo `dev up` para subir `redis` e checar health.
 - **[adapter]** Documentar whitelist e tipos suportados; manter `WA_ONLY_CONTACTS` claro durante testes.
 
 ## Plano para o futuro (roadmap)
 - **Fase 1 (Receptivo)**
   - Refinar funil em `app/domain/realestate/conversation_handlers.py`:
     - Textos/tom (saudação, LGPD, coleta, finalização) e transições entre estágios.
     - Heurística de cidade/UF e tipo; listagem até 3 cards com `ref_code/external_id/id`.
   - Persistência de status e eventos:
     - `status`: `novo`, `qualificado`, `agendamento_pendente`, `agendado`, `sem_resposta_24h`.
     - Eventos: `lead.created`, `lead.updated`, `visit.requested`, `followup.sent`.
 - **Fase 2 (Campanhas/Simulador)** Tela com filtros e disparo simulado via `adapter-wa/` com auditoria.
 - **Fases seguintes** Templates Meta, integrações (CRM/e-mail), notificações para equipe, métricas e relatórios.
 
 ## Próximas ações imediatas
 - **[ajustar funil conversacional]** Iterar nos handlers conforme conversas reais (mensagens, transições, validações).
 
## Melhorias implementadas (v2 - LLM)

### Detecção aprimorada via LLM
- **Valores por extenso**: "cem mil" → 100000, "dois mil" → 2000 (fallback manual implementado)
- **Abreviações de tipo**: "ap", "apto" → apartment (fallback com match exato)
- **Sinônimos expandidos**: "outras opções", "outro imovel" → próximo
- **Nova intenção**: `ajustar_criterios` detecta "vamos ajustar", "mudar critérios", "refazer busca"

### Fluxo de refinamento
- **Estágio `awaiting_refinement`**: após "sem resultados" ou "não há mais imóveis"
- **Mantém LGPD**: não reseta consentimento ao ajustar critérios
- **Handler `handle_refinement`**: detecta intenção de nova busca e reinicia do estágio `awaiting_purpose`

### Fallbacks robustos
- Todas as funções de detecção LLM têm fallback para regex
- Se LLM falhar, sistema continua funcionando com regex original
- `extract_price()` tem mapa manual de valores por extenso (cem mil, um milhão, etc.)
- `detect_property_type()` tem match exato para abreviações (ap, apto)

## Melhorias implementadas (v3 - Refinamento Inteligente)

### Extração de preços corrigida
- **Problema**: "90 mil" era convertido para 900.000 (LLM errava)
- **Solução**: Priorizar regex/extenso sobre LLM
  - `extenso_map` expandido com 40+ variações (90 mil, noventa mil, 90k, etc.)
  - LLM usado apenas como último recurso
  - Logs detalhados em cada etapa (extenso → regex → LLM)
- **Status**: RESOLVIDO

### Refinamento inteligente com manutenção de contexto
- **Problema**: Ao refinar critérios, bot perguntava tudo novamente
- **Solução**: 
  - Mantém critérios anteriores (cidade, tipo, finalidade)
  - Permite ajuste pontual (só preço, só quartos, etc.)
  - Busca silenciosa após refinamento (sem "Vou buscar...")
- **Status**: RESOLVIDO

### Validação anti-alucinação do LLM
- **Problema**: LLM extraía `tipo: "ajustar"` quando usuário dizia "ajustar criterios"
- **Solução**: 
  - Filtrar entidades genéricas (`"ajustar"`, `"null"`)
  - Validar palavra-chave explícita antes de aceitar mudança de tipo
  - Exemplo: só aceita `tipo: "apartamento"` se texto contém "apartamento"
- **Status**: RESOLVIDO

### Refinamento genérico tratado
- **Problema**: "ajustar criterio" iniciava busca vazia
- **Solução**: 
  - Detecta intenção genérica e pergunta "O que deseja ajustar?"
  - Mostra critérios atuais e exemplos
  - Permite ajuste durante visualização de imóveis
- **Status**: RESOLVIDO

### Aplicação direta de quartos
- **Problema**: "quero 3 quartos" → bot perguntava "Quantos quartos?"
- **Solução**: 
  - Extrai `bedrooms` do LLM e aplica direto
  - Busca silenciosa após aplicar
  - Sem perguntas redundantes
- **Status**: RESOLVIDO

### Erro NoneType em descrição
- **Problema**: `TypeError: object of type 'NoneType' has no len()` quando `prop.description = None`
- **Solução**: 
  - Validar `descricao` antes de `len()`
  - Fallback para "Sem descrição disponível."
- **Status**: RESOLVIDO

### Anti-eco funcionando
- Mensagens do bot não são mais reprocessadas como entrada do usuário
- Registra `lastBotByChat` ANTES de enviar (evita race condition)

## Melhorias implementadas (v4 - Refinamento Robusto e UX)

### Personalização com nome do usuário
- **Problema**: Bot não usava nome do usuário nas mensagens
- **Solução**: 
  - Extrai nome via LLM no estágio `awaiting_name`
  - Armazena em `state["user_name"]`
  - Usa em todas as mensagens: "Rodrigo, gostou deste imóvel?"
- **Status**: RESOLVIDO

### Detecção genérica de refinamento
- **Problema**: Cada critério tinha lógica duplicada em múltiplos handlers
- **Solução**: 
  - Criada função centralizada `_detect_refinement_intent()`
  - Detecta QUALQUER critério: quartos, preço, tipo, cidade, bairro, finalidade
  - Lógica: se valor especificado → aplica direto, senão → pergunta
  - Usado em `handle_property_feedback` e `handle_visit_decision`
- **Status**: RESOLVIDO

### Mudança de finalidade com reset de preços
- **Problema**: Ao mudar de COMPRA → ALUGUEL, preços ficavam incompatíveis (R$ 400.000 para aluguel!)
- **Solução**: 
  - Detecta mudança de finalidade
  - Reseta `price_min` e `price_max`
  - Explica ao cliente: "Como você mudou de COMPRA para ALUGUEL, preciso reajustar os valores"
  - Mantém outros critérios (tipo, cidade, bairro, quartos)
- **Status**: RESOLVIDO

### Priorização de regex sobre LLM
- **Problema**: LLM retornava `tipo: "house"` para input "ap"
- **Solução**: 
  - `detect_property_type()` prioriza regex exato antes de LLM
  - `handle_type()` prioriza detecção local sobre LLM entities
  - Regex: "ap" → "apartment" (100% confiável)
- **Status**: RESOLVIDO

### Busca exata por número de quartos
- **Problema**: Busca usava `bedrooms >= X` (retornava imóveis com mais quartos)
- **Solução**: 
  - Mudado para `bedrooms == X` (busca exata)
  - Se não encontrar, retorna "não encontrei imóveis com 4 quartos"
- **Status**: RESOLVIDO

### Função format_no_more_properties criada
- **Problema**: `AttributeError: format_no_more_properties` ao clicar "próximo" no último imóvel
- **Solução**: 
  - Criada função em `message_formatters.py`
  - Mensagem: "Esses foram todos os imóveis disponíveis. Gostaria de ajustar os critérios?"
- **Status**: RESOLVIDO

### Textos com opção "ajustar critérios"
- **Problema**: Mensagens não mencionavam opção de ajustar critérios
- **Solução**: 
  - Card do imóvel: "Digite 'sim', 'próximo' ou 'ajustar critérios'"
  - Detalhes: "Digite 'agendar', 'próximo' ou 'ajustar critérios'"
  - Melhora descoberta de funcionalidade
- **Status**: RESOLVIDO

### Arquitetura de refinamento escalável
- **Princípios aplicados**:
  - ✅ DRY: Lógica centralizada em `_detect_refinement_intent()`
  - ✅ Escalável: Fácil adicionar novos critérios
  - ✅ Inteligente: Detecta se valor foi especificado
  - ✅ Conversacional: Pergunta quando necessário
  - ✅ Silencioso: Busca sem mensagens redundantes
  - ✅ Transparente: Explica por que está perguntando novamente

## Melhorias implementadas (v5 - Agendamento e Códigos de Imóveis)

### Sistema de códigos de referência (ref_code)
- **Problema**: Imóveis não tinham código de referência acessível para busca direta
- **Solução**: 
  - Backfill de 397 imóveis: `external_id` → `ref_code`
  - Extração robusta de códigos: A1234, ND12345, URLs (/imovel/A738), links
  - Busca direta por `ref_code` sem fallback
  - Script `scripts/backfill_ref_codes.py` para popular códigos
- **Status**: RESOLVIDO

### Fluxo de agendamento completo
- **Implementado**:
  - Bifurcação: "Tem imóvel em mente?" → código direto ou busca assistida
  - Validação de código com feedback claro
  - Confirmação de telefone com detecção expandida ("está correto", "certo", "confirmo")
  - Parse de data em linguagem natural: "amanhã", "segunda", "25/10"
  - Parse de horário: "14h", "manhã", "tarde", "14:30"
  - Criação de `VisitSchedule` e atualização de Lead para status "agendado"
  - Notificação registrada (pronta para integração WhatsApp)
- **Serviços criados**:
  - `app/services/visit_service.py` — parse de data/hora, criação de agendamentos
  - `app/services/notification_service.py` — placeholders para notificações
- **Status**: FUNCIONAL

### Detecção híbrida (hardcode + LLM)
- **Problema**: Respostas como "fazer agendamento" ou "está correto" não eram reconhecidas
- **Solução**: 
  - Todas as funções de detecção usam hardcode primeiro (rápido) + LLM como reforço
  - `detect_yes_no()`: expandido com "correto", "certo", "confirmo", "perfeito"
  - `detect_schedule_intent()`: "agendar", "visita", "marcar", "fazer agendamento"
  - `detect_consent()`: prioriza regex local antes de LLM
- **Status**: RESOLVIDO

### Fluxo "Não encontrei imóvel"
- **Implementado**:
  - Opção explícita na apresentação de imóveis
  - Ao escolher: Lead.status = "sem_imovel_disponivel"
  - Persiste dados: imóveis exibidos, detalhados, filtros, timestamps
  - Encerra conversa com mensagem de suporte
- **Status**: FUNCIONAL

### Recusa de agendamento
- **Implementado**:
  - Detecta recusa: "não quero agendar", "depois eu vejo", "mais tarde"
  - Classifica lead como "qualificado" via `LeadService.mark_qualified()`
  - Encerra conversa mantendo dados do lead
- **Status**: FUNCIONAL

### Configuração de timeout para leads "novo"
- **Implementado**:
  - `LEAD_NEW_INACTIVITY_MINUTES=120` em `app/core/config.py`
  - Corte no estágio A2 (antes de `awaiting_name`)
  - Após 120min sem resposta → status "novo"
- **Status**: CONFIGURADO

### Correções de modelo e banco
- **Ajustes**:
  - Modelo `Lead`: FK `contact_id` removida temporariamente (tabela contacts não existe)
  - Modelo `VisitSchedule`: ajustado para corresponder à estrutura real da tabela
  - Campos: `scheduled_datetime`, `scheduled_date`, `scheduled_time`, `contact_phone`, `contact_name`
- **Status**: RESOLVIDO

## Referências de código
- `app/main.py` — roteamento e middleware de erro.
- `app/api/routes/mcp.py` — endpoint `POST /execute`.
- `app/api/deps.py` — injeção de `ConversationStateService` com Redis.
- `app/services/conversation_state.py` — `get_state/set_state/clear_state` no Redis.
- `app/services/llm_service.py` — cliente Ollama para extração de intenção/entidades via LLM.
- `app/services/visit_service.py` — parse de data/hora natural, criação de agendamentos.
- `app/services/notification_service.py` — notificações (placeholder para WhatsApp).
- `app/services/lead_service.py` — criação e classificação de leads.
- `app/domain/realestate/detection_utils.py` — detecção híbrida (hardcode + LLM).
- `app/domain/realestate/conversation_handlers.py` — handlers de estágios com agendamento.
- `app/domain/realestate/models.py` — modelos Lead, VisitSchedule, Property.
- `adapter-wa/index.js` — MCP_URL, whitelist, anti-eco e tratamento de mensagens.
- `scripts/backfill_ref_codes.py` — script para popular ref_code a partir de external_id.
- `tests/test_mcp_leads.py` — testes do endpoint MCP (modo `tool`).
- `tests/test_llm_detection.py` — testes de detecção via LLM (requer Ollama).
- `test_agendamento.py` — teste completo do fluxo de agendamento (10 etapas)
