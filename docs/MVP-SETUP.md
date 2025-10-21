# 🚀 Setup do MVP - AtendeJá ND Imóveis

**Versão:** 1.0  
**Última atualização:** 21/10/2025

---

## 📋 Pré-requisitos

Para executar o MVP do chatbot imobiliário, você precisa ter instalado:

- **Docker** (para Redis e PostgreSQL)
- **Python 3.11+** (para o backend FastAPI)
- **Node.js 18+** (para o adapter WhatsApp)
- **Ollama** (para o LLM local - opcional mas recomendado)

---

## 🐳 1. Containers Docker (Obrigatórios)

### **Containers necessários:**

```bash
# Verificar containers existentes
docker ps -a

# Você deve ter:
# - atendeja-redis (porta 6379)
# - atendeja-postgres (porta 5432)
```

### **Iniciar containers:**

```bash
# Redis (armazenamento de estado da conversa)
docker start atendeja-redis

# PostgreSQL (banco de dados principal)
docker start atendeja-postgres

# Verificar se estão rodando
docker ps
```

### **Status esperado:**
```
CONTAINER ID   IMAGE                COMMAND                  STATUS
115558453d7b   redis:7-alpine       "docker-entrypoint..."   Up (healthy)
a3d415f1829f   postgres:16-alpine   "docker-entrypoint..."   Up (healthy)
```

---

## 🔧 2. Backend FastAPI

### **Localização:**
```
c:\rodrigo\prototipo ND Imoveis\atendeJa ND Imoveis\
```

### **Iniciar:**

```bash
# Ativar ambiente virtual
.venv\Scripts\activate

# Instalar dependências (primeira vez)
pip install -r requirements.txt

# Executar servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### **Verificar:**
- URL: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

---

## 📱 3. Adapter WhatsApp

### **Localização:**
```
c:\rodrigo\prototipo ND Imoveis\atendeJa ND Imoveis\adapter-wa\
```

### **Configurar `.env`:**

```env
# Backend MCP
MCP_URL=http://localhost:8000/api/v1/mcp/execute
MCP_TOKEN=seu_token_aqui
MCP_TENANT_ID=default

# WhatsApp
WA_SESSION_NAME=atendeja-wa
WA_RATE_LIMIT_PER_CONTACT_SECONDS=2
WA_ALLOW_FROM_ME=true
WA_CLEAR_STATE_ON_START=true

# Whitelist (opcional - deixe vazio para atender todos)
WA_ONLY_CONTACTS=5511964442592
```

### **Iniciar:**

```bash
# Instalar dependências (primeira vez)
npm install

# Executar adapter
npm start
```

### **Primeiro uso:**
1. Escanear QR code que aparece no terminal
2. Aguardar mensagem "Cliente pronto (ready)"
3. Enviar "ola" no WhatsApp para testar

---

## 🤖 4. Ollama (LLM Local - Opcional)

### **Instalação:**
- Download: https://ollama.ai
- Instalar e executar

### **Modelo recomendado:**

```bash
# Baixar modelo leve e rápido
ollama pull gemma2:2b

# Ou modelo mais robusto
ollama pull llama3.2:3b
```

### **Configurar no `.env` do backend:**

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_DEFAULT_MODEL=gemma2:2b
LLM_ENRICH_MCP=true
```

### **Verificar:**
```bash
# Testar Ollama
curl http://localhost:11434/api/tags
```

---

## ✅ Checklist de Inicialização

Execute nesta ordem:

- [ ] **1. Docker**
  ```bash
  docker start atendeja-redis atendeja-postgres
  docker ps  # Verificar status
  ```

- [ ] **2. Ollama** (opcional)
  ```bash
  ollama serve  # Se não estiver rodando
  ollama list   # Verificar modelos instalados
  ```

- [ ] **3. Backend FastAPI**
  ```bash
  cd "c:\rodrigo\prototipo ND Imoveis\atendeJa ND Imoveis"
  .venv\Scripts\activate
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
  ```

- [ ] **4. Adapter WhatsApp**
  ```bash
  cd "c:\rodrigo\prototipo ND Imoveis\atendeJa ND Imoveis\adapter-wa"
  npm start
  ```

- [ ] **5. Escanear QR Code** (primeira vez ou após limpar sessão)

- [ ] **6. Testar** enviando "ola" no WhatsApp

---

## 🔍 Troubleshooting

### **Erro: Redis connection refused**
```bash
# Solução: Iniciar Redis
docker start atendeja-redis
docker logs atendeja-redis  # Ver logs
```

### **Erro: PostgreSQL connection refused**
```bash
# Solução: Iniciar PostgreSQL
docker start atendeja-postgres
docker logs atendeja-postgres  # Ver logs
```

### **Erro: MCP 500 Internal Server Error**
- Verificar logs do backend FastAPI
- Verificar se Redis e PostgreSQL estão rodando
- Verificar se Ollama está acessível (se LLM_ENRICH_MCP=true)

### **WhatsApp não conecta**
```bash
# Limpar sessão e tentar novamente
rm -rf .wwebjs_auth
npm start
```

### **LLM não responde**
```bash
# Verificar Ollama
curl http://localhost:11434/api/tags

# Baixar modelo se necessário
ollama pull gemma2:2b
```

---

## 📊 Portas Utilizadas

| Serviço          | Porta | URL                              |
|------------------|-------|----------------------------------|
| Backend FastAPI  | 8000  | http://localhost:8000            |
| PostgreSQL       | 5432  | localhost:5432                   |
| Redis            | 6379  | localhost:6379                   |
| Ollama           | 11434 | http://localhost:11434           |

---

## 🎯 Fluxo de Teste Rápido

1. **Iniciar tudo** (seguir checklist acima)
2. **Enviar no WhatsApp:**
   ```
   ola
   ```
3. **Resposta esperada:**
   ```
   Bom dia! Eu sou o assistente virtual da ND Imóveis...
   ```
4. **Testar comandos:**
   - `ajuda` - Ver comandos disponíveis
   - `refazer` - Recomeçar conversa
   - Seguir fluxo completo de busca

---

## 📝 Logs Importantes

### **Backend:**
```bash
# Ver logs em tempo real
tail -f logs/app.log  # Se configurado
# Ou ver no terminal onde uvicorn está rodando
```

### **Adapter WhatsApp:**
```bash
# Logs aparecem no terminal
# Procurar por:
# ✅ Processando fromMe para: ...
# 📤 Enviando resposta...
# ❌ Erro ao processar mensagem...
```

### **Docker:**
```bash
# Ver logs dos containers
docker logs atendeja-redis
docker logs atendeja-postgres
```

---

## 🔐 Segurança (Produção)

**Não esquecer de configurar:**

- `MCP_API_TOKEN` - Token de autenticação do MCP
- `AUTH_JWT_SECRET` - Secret para JWT
- `WA_WEBHOOK_SECRET` - Secret para validação de webhooks
- Remover `WA_ALLOW_FROM_ME=true` em produção
- Configurar whitelist de contatos se necessário

---

## 📚 Documentação Adicional

- **Arquitetura:** `/docs/CHAT-PLAN.md`
- **Infraestrutura:** `/docs/INFRAESTRUTURA-CLIENTE.md`
- **Imóveis:** `/docs/REAL_ESTATE_PLAN.md`
- **API Docs:** http://localhost:8000/docs

---

## 🆘 Suporte

Em caso de problemas:

1. Verificar todos os serviços estão rodando (checklist)
2. Verificar logs de cada componente
3. Verificar portas não estão em conflito
4. Reiniciar containers se necessário
5. Limpar estado do Redis: `docker exec -it atendeja-redis redis-cli FLUSHDB`

---

**Última revisão:** 21/10/2025  
**Autor:** Sistema AtendeJá ND Imóveis
