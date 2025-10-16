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
 - **[engenharia]**
   - Uniformizar `admin_realestate.py` para `Depends(get_db)` quando aplicável.
   - Mapear conflitos para `409 Conflict` nos endpoints administrativos.
   - Documentar padrão de dependência de DB e overrides de teste no `README-PT.md`.
 
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
 
 ## Problemas conhecidos (v2)
 
 ### ❌ CRÍTICO: Valores por extenso não funcionando
 - **Sintoma**: "cem mil" retorna "Não consegui identificar o valor"
 - **Causa investigada**: 
   - LLM (Ollama) pode estar indisponível ou com timeout
   - Fallback implementado com mapa `extenso_map` em `extract_price()`
   - Logs adicionados mas não aparecem no servidor (código pode não estar sendo executado)
   - Tentativa de renomear `detection_utils_llm.py` → `detection_utils.py` para forçar uso
 - **Status**: NÃO RESOLVIDO
 - **Próximos passos**: 
   - Verificar se API está importando módulo correto
   - Adicionar print() direto no código (não depende de structlog)
   - Testar função isoladamente com script Python
 
 ### ⚠️ Abreviações de tipo
 - **Sintoma**: "ap" retorna "Não entendi o tipo"
 - **Causa**: Mesmo problema de valores por extenso (código pode não estar sendo executado)
 - **Status**: NÃO RESOLVIDO
 
 ### ✅ Anti-eco funcionando
 - Mensagens do bot não são mais reprocessadas como entrada do usuário
 - Registra `lastBotByChat` ANTES de enviar (evita race condition)
 
 ## Referências de código
 - `app/main.py` — roteamento e middleware de erro.
 - `app/api/routes/mcp.py` — endpoint `POST /execute`.
 - `app/api/deps.py` — injeção de `ConversationStateService` com Redis.
 - `app/services/conversation_state.py` — `get_state/set_state/clear_state` no Redis.
 - `app/services/llm_service.py` — cliente Ollama para extração de intenção/entidades via LLM.
 - `app/domain/realestate/detection_utils.py` — detecção via LLM com fallback robusto (renomeado de `detection_utils_llm.py`).
 - `app/domain/realestate/conversation_handlers.py` — handlers de estágios (usa `detection_utils_llm`).
 - `adapter-wa/index.js` — MCP_URL, whitelist, anti-eco e tratamento de mensagens.
 - `tests/test_mcp_leads.py` — testes do endpoint MCP (modo `tool`).
 - `tests/test_llm_detection.py` — testes de detecção via LLM (requer Ollama).
