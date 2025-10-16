# Adapter WA (whatsapp-web.js) — POC local

Este adaptador conecta ao WhatsApp Web usando whatsapp-web.js, mantém sessão persistida (LocalAuth) e encaminha mensagens para o backend (MCP /api/v1/mcp/execute). Use apenas para desenvolvimento.

## Pré-requisitos
- Node.js LTS
- Backend em execução (FastAPI) e acessível (ex.: http://localhost:8000)

## Instalação
```bash
cd adapter-wa
npm install
```

## Configuração
Crie um arquivo `.env` dentro de `adapter-wa/` com:
```
MCP_URL=http://localhost:8000/api/v1/mcp/execute
MCP_TOKEN=
MCP_TENANT_ID=default
WA_SESSION_NAME=atendeja-wa
WA_QR_FILE=qr.png
WA_RATE_LIMIT_PER_CONTACT_SECONDS=2
```

## Execução
```bash
npm start
# ou
node index.js
```
Escaneie o QR exibido no terminal ou abra `qr.png`.

## Uso
- Envie uma mensagem (para você mesmo ou de outro número)
- O adaptador repassa o texto para o MCP do backend
- A resposta do MCP é enviada de volta ao mesmo chat

## Observações
- Ignora grupos por padrão (ids que terminam com `@g.us`).
- Se a sessão apresentar problemas, apague a pasta `.wwebjs_auth/` para forçar novo QR.
- Este projeto é para POC. Em produção, prefira provedores oficiais (WhatsApp Cloud API) que já estão integrados no backend.
