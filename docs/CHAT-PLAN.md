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
 
 ## Referências de código
 - `app/main.py` — roteamento e middleware de erro.
 - `app/api/routes/mcp.py` — endpoint `POST /execute`.
 - `app/api/deps.py` — injeção de `ConversationStateService` com Redis.
 - `app/services/conversation_state.py` — `get_state/set_state/clear_state` no Redis.
 - `app/services/llm_service.py` — cliente Ollama para extração de intenção/entidades via LLM.
 - `app/domain/realestate/detection_utils_llm.py` — detecção via LLM (substitui regex de `detection_utils.py`).
 - `app/domain/realestate/conversation_handlers.py` — handlers de estágios (usa `detection_utils_llm`).
 - `adapter-wa/index.js` — MCP_URL, whitelist, anti-eco e tratamento de mensagens.
 - `tests/test_mcp_leads.py` — testes do endpoint MCP (modo `tool`).
 - `tests/test_llm_detection.py` — testes de detecção via LLM (requer Ollama).
