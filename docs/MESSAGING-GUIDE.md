# Guia de Mensageria (WhatsApp Cloud) — Base Implementada

Este documento registra exatamente onde paramos e qual é o plano de próximos passos, para retomarmos de forma segura quando o cliente liberar esta etapa.

## O que foi implementado (backend)
- Rate limiting configurável (por contato e global)
  - Arquivos: `app/messaging/limits.py`, `app/core/config.py`
  - Flags:
    - `WA_RATE_LIMIT_PER_CONTACT_SECONDS` (padrão 2s)
    - `WA_RATE_LIMIT_GLOBAL_PER_MINUTE` (padrão 60)
- Opt-out (lista de supressão) e Auditoria de envios
  - Modelos: `SuppressedContact`, `MessageLog` em `app/repositories/models.py`
  - Migração: `migrations/versions/7f2d3a1c9b2a_messaging_audit_optout.py`
- Janela de 24h (Meta)
  - Guard no `MetaCloudProvider.send_text()` — bloqueia texto livre fora da janela; `send_template()` sempre permitido.
  - Arquivo: `app/messaging/meta.py`
- Endpoints Admin (após login)
  - `GET /admin/messaging/logs`
  - `POST /admin/messaging/suppress`
  - `DELETE /admin/messaging/suppress?wa_id=...`
  - `GET /admin/messaging/window-status?wa_id=...`
  - Testes de envio (para validação):
    - `POST /admin/messaging/test-template`
    - `POST /admin/messaging/test-text` (respeita janela 24h)

## Como aplicar (migrar e subir)
1. Migração
```
poetry run alembic upgrade head
```
2. Subir API
```
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
3. Docs
- Swagger: `http://localhost:8000/docs`

## Variáveis de ambiente relevantes (`.env`)
- Credenciais Meta (preencher quando o cliente liberar):
```
WA_TOKEN=<TOKEN_REAL_DA_META>
WA_PHONE_NUMBER_ID=<PHONE_NUMBER_ID_REAL>
WA_API_BASE=https://graph.facebook.com/v20.0
```
- Boas práticas (valores padrão já definidos):
```
WINDOW_24H_ENABLED=true
WINDOW_24H_HOURS=24
WA_RATE_LIMIT_PER_CONTACT_SECONDS=2
WA_RATE_LIMIT_GLOBAL_PER_MINUTE=60
```

## Como testar (PowerShell)
Definir variáveis:
```powershell
$BASE = "http://localhost:8000"
$TOKEN = "<JWT_ADMIN>"
$WAID  = "5511999999999"  # exemplo
```
- Status da janela:
```powershell
Invoke-RestMethod -Method GET -Uri "$BASE/admin/messaging/window-status?wa_id=$WAID" -Headers @{ Authorization = "Bearer $TOKEN" }
```
- Adicionar opt-out:
```powershell
$body = @{ wa_id = $WAID; reason = "opt-out manual" } | ConvertTo-Json
Invoke-RestMethod -Method POST -Uri "$BASE/admin/messaging/suppress" -Headers @{ Authorization = "Bearer $TOKEN"; "Content-Type" = "application/json" } -Body $body
```
- Remover opt-out:
```powershell
Invoke-RestMethod -Method DELETE -Uri "$BASE/admin/messaging/suppress?wa_id=$WAID" -Headers @{ Authorization = "Bearer $TOKEN" }
```
- Enviar TEMPLATE (gera log; requer credenciais Meta válidas):
```powershell
$body = @{ wa_id = $WAID; template_name = "hello_world"; language = "pt_BR"; components = @() } | ConvertTo-Json
Invoke-RestMethod -Method POST -Uri "$BASE/admin/messaging/test-template" -Headers @{ Authorization = "Bearer $TOKEN"; "Content-Type" = "application/json" } -Body $body
```
- Enviar TEXTO (bloqueia fora da janela):
```powershell
$body = @{ wa_id = $WAID; body = "Teste de mensagem livre" } | ConvertTo-Json
Invoke-RestMethod -Method POST -Uri "$BASE/admin/messaging/test-text" -Headers @{ Authorization = "Bearer $TOKEN"; "Content-Type" = "application/json" } -Body $body
```
- Consultar logs:
```powershell
(Invoke-RestMethod -Method GET -Uri "$BASE/admin/messaging/logs?limit=50&offset=0" -Headers @{ Authorization = "Bearer $TOKEN" }) | ConvertTo-Json -Depth 5
```

## Onde paramos
- Base técnica pronta e validada localmente (migrada, endpoints ativos, logs e supressão funcionais).
- Sem credenciais reais da Meta no `.env` (aguardando cliente).
- Sem tela de UI Admin para mensageria (opcional para próxima etapa).

## Próximos passos (quando o cliente aprovar)
1. Preencher `.env` com `WA_TOKEN` e `WA_PHONE_NUMBER_ID` reais e reiniciar API.
2. Validar envio de template real; confirmar que `MessageLog` registra `sent`.
3. (Opcional) Criar tela Admin para:
   - Listar `MessageLog` (filtros por `to`/status/data);
   - Gerenciar opt-out (adicionar/remover);
   - Consultar `window-status` para um `wa_id`.
4. (Opcional) Métricas e alertas (ex.: taxa de erro, volume por minuto, aquecimento do número).

## Riscos e salvaguardas
- Fora da janela de 24h: apenas templates aprovados (guard já implementado em `send_text`).
- Rate limit: evitar flood local/global (valores ajustáveis por env).
- Opt-out: bloqueio imediato para reduzir denúncias e risco de banimento.

---
Atualizado em: <INSERIR DATA AO COMMIT>
