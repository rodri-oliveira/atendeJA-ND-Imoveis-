# Infraestrutura para Produção – AtendeJá Chatbot

## 💰 Custos Mensais

### Opção Econômica (Recomendada para MVP)

| Serviço | Provedor | Custo/mês | Status |
|---------|----------|-----------|--------|
| **PostgreSQL** | Neon | **GRÁTIS** (10GB) | Obrigatório |
| **Redis** | Upstash | **GRÁTIS** (10k req/dia) | Obrigatório |
| **Backend API** | Render | **US$ 7** (~R$ 35) | Obrigatório |
| **Frontend Web** | Render Static | **GRÁTIS** | Obrigatório |
| **Imagens** | Cloudflare R2 | **~R$ 5** (100GB) | Opcional (MVP usa URLs) |

**TOTAL: R$ 35/mês (MVP até 1.000 conversas)**

### Cenários de Crescimento

| Volume | Render | WhatsApp | Redis | **Total/mês** |
|--------|--------|----------|-------|---------------|
| 1.000 conversas | R$ 35 | R$ 0 | R$ 0 | **R$ 35** |
| 5.000 conversas | R$ 35 | R$ 60 | R$ 0 | **R$ 95** |
| 10.000 conversas | R$ 125 | R$ 135 | R$ 50 | **R$ 310** |

---

## 📦 Componentes do Sistema

### 1. Backend API (Render - $7/mês)
- FastAPI (Python 3.11)
- Worker Celery (processamento assíncrono)
- Webhook WhatsApp
- Gestão de imóveis e leads
- Proxy de imagens

**Especificações:**
- 512MB RAM
- Always-on (não hiberna)
- Deploy automático via GitHub

### 2. Banco de Dados (Neon - GRÁTIS)
- PostgreSQL 16
- 10GB storage
- Backups automáticos
- Connection pooling

**Capacidade:**
- ~100.000 imóveis
- ~500.000 mensagens
- ~50.000 leads

### 3. Redis (Upstash - GRÁTIS)
- Filas de mensagens Celery
- Cache de sessões
- Rate limiting
- 10.000 comandos/dia

### 4. Frontend Admin (Render Static - GRÁTIS)
- Interface web responsiva
- Gestão de imóveis
- Visualização de leads
- Dashboard de métricas

### 5. WhatsApp Business API
- **IMPORTANTE**: Necessário WhatsApp Business API (não o app grátis)
- 1.000 conversas/mês grátis
- Após limite: R$ 0,15/conversa (~R$ 135 para 10k conversas)

---

## 🔑 Credenciais Necessárias do Cliente

### ⚠️ Pré-requisito: WhatsApp Business API

**O cliente DEVE ter WhatsApp Business API configurado:**

| Tipo | Funciona? | Como identificar |
|------|-----------|------------------|
| WhatsApp Business (app grátis) | ❌ NÃO | Usa WhatsApp no celular manualmente |
| WhatsApp Business API | ✅ SIM | Já tem integração com sistemas/CRM |

**Se o cliente não tem API:**
- Solicitar acesso via Meta Business Suite
- Prazo: 3-7 dias úteis
- Custo: 1.000 conversas/mês grátis

---

### WhatsApp Business API - Credenciais

O cliente precisa fornecer:

#### 1. Token de Acesso (WA_TOKEN)
- **Onde encontrar**: Meta Business Suite → Configurações → WhatsApp → Token de acesso
- **Formato**: `EAAxxxxxxxxxxxxxxxxxxxxx`
- **Uso**: Autenticação na API do WhatsApp

#### 2. Phone Number ID (WA_PHONE_NUMBER_ID)
- **Onde encontrar**: Meta Business Suite → WhatsApp → Números de telefone
- **Formato**: Número de 15 dígitos (ex: `123456789012345`)
- **Uso**: Identificar o número que envia/recebe mensagens

#### 3. Número do WhatsApp
- **Formato**: +55 11 99999-9999
- **Status**: Deve estar verificado e conectado no Meta Business

#### 4. Verify Token (WA_VERIFY_TOKEN)
- **Definição**: Você cria (ex: `meutoken123seguro`)
- **Uso**: Validar webhook no Meta Business

#### 5. Webhook Secret (Opcional)
- **Onde encontrar**: Meta Business Suite → Configurações de webhook
- **Uso**: Validar assinatura das mensagens

---

## 🚀 Setup Passo a Passo

### Fase 1: Criar Contas (15 minutos)

#### 1.1 Neon PostgreSQL (5 min)
1. Acessar: https://neon.tech
2. Criar conta (GitHub login recomendado)
3. Criar novo projeto: `atendeja-chatbot`
4. Copiar connection string: `postgresql://user:pass@host/db`

#### 1.2 Upstash Redis (5 min)
1. Acessar: https://upstash.com
2. Criar conta
3. Criar database Redis: `atendeja-redis`
4. Copiar connection string: `redis://default:pass@host:port`

#### 1.3 Render (5 min)
1. Acessar: https://render.com
2. Criar conta (GitHub login recomendado)
3. Conectar repositório GitHub do projeto

---

### Fase 2: Deploy Backend (20 minutos)

#### 2.1 Criar Web Service no Render
1. Dashboard → New → Web Service
2. Conectar repositório: `atendeJa-ND-Imoveis`
3. Configurações:
   - **Name**: `atendeja-api`
   - **Environment**: `Docker`
   - **Plan**: Starter ($7/mês)
   - **Region**: Oregon (mais barato)

**Limites do Starter:**
- 512MB RAM (suficiente para 50 req/s)
- 100GB bandwidth/mês (suficiente para ~10k conversas)
- Celery worker roda no mesmo processo (OK para MVP)

#### 2.2 Configurar Variáveis de Ambiente

```bash
# Ambiente
APP_ENV=production
DEFAULT_TENANT_ID=default

# Banco de Dados (Neon)
DATABASE_URL_OVERRIDE=postgresql://user:pass@host/db

# Redis (Upstash)
REDIS_HOST=host.upstash.io
REDIS_PORT=6379
REDIS_PASSWORD=sua-senha
REDIS_DB=0

# Autenticação
AUTH_JWT_SECRET=gerar-string-aleatoria-segura-aqui
AUTH_JWT_EXPIRE_MINUTES=60
AUTH_SEED_ADMIN_EMAIL=admin@cliente.com.br
AUTH_SEED_ADMIN_PASSWORD=SenhaForte123!

# WhatsApp (do cliente)
WA_PROVIDER=meta
WA_TOKEN=EAAxxxxxxxxxxxxx
WA_PHONE_NUMBER_ID=123456789012345
WA_API_BASE=https://graph.facebook.com/v20.0
WA_VERIFY_TOKEN=meutoken123seguro
WA_WEBHOOK_SECRET=opcional

# Rate Limiting
WINDOW_24H_ENABLED=true
WINDOW_24H_HOURS=24
WA_RATE_LIMIT_PER_CONTACT_SECONDS=2
WA_RATE_LIMIT_GLOBAL_PER_MINUTE=60

# Imóveis (produção)
RE_READ_ONLY=false
```

#### 2.3 Deploy
1. Clicar em "Create Web Service"
2. Aguardar build (5-10 minutos)
3. Anotar URL: `https://atendeja-api.onrender.com`

---

### Fase 3: Deploy Frontend (10 minutos)

#### 3.1 Criar Static Site no Render
1. Dashboard → New → Static Site
2. Conectar mesmo repositório
3. Configurações:
   - **Name**: `atendeja-web`
   - **Build Command**: `cd frontend/ui && npm install && npm run build`
   - **Publish Directory**: `frontend/ui/dist`

#### 3.2 Configurar Variável e CORS

**Variável de ambiente:**
```bash
VITE_API_URL=https://atendeja-api.onrender.com
```

**IMPORTANTE: Configurar CORS no Backend**
Adicionar no `app/main.py`:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://atendeja-web.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### 3.3 Deploy
1. Clicar em "Create Static Site"
2. Aguardar build (3-5 minutos)
3. Anotar URL: `https://atendeja-web.onrender.com`

---

### Fase 4: Configurar WhatsApp Webhook (10 minutos)

#### 4.1 No Meta Business Suite
1. Acessar: https://business.facebook.com
2. Configurações → WhatsApp → Configuração
3. Seção "Webhook"

#### 4.2 Configurar Webhook
- **URL de callback**: `https://atendeja-api.onrender.com/webhook/whatsapp`
- **Token de verificação**: `meutoken123seguro` (mesmo do `WA_VERIFY_TOKEN`)
- **Eventos para assinar**:
  - ✅ `messages`
  - ✅ `message_status`

#### 4.3 Testar
1. Enviar mensagem de teste para o número WhatsApp
2. Verificar logs no Render: Dashboard → Logs
3. Confirmar recebimento da mensagem

---

### Fase 5: Executar Migrações (5 minutos)

#### 5.1 Via Render Shell
1. Dashboard → atendeja-api → Shell
2. Executar:
```bash
alembic upgrade head
```

#### 5.2 Verificar
- Acessar Neon dashboard
- Confirmar criação das tabelas:
  - `users`, `tenants`
  - `re_properties`, `re_property_images`
  - `re_leads`, `re_inquiries`
  - `conversation_events`, `message_audit`

---

## 📊 Capacidade e Limites

### Free Tier (Início)

| Recurso | Limite | Suficiente para |
|---------|--------|-----------------|
| **PostgreSQL** | 10GB | 100.000 imóveis |
| **Redis** | 10k comandos/dia | 300 conversas/dia |
| **API** | 512MB RAM | 50 req/s |
| **WhatsApp** | 1.000 conversas/mês | 30-40 conversas/dia |

### Quando Escalar?

**Upgrade PostgreSQL** (quando atingir 8GB):
- Neon Pro: $19/mês (50GB)

**Upgrade Redis** (quando passar 8k comandos/dia):
- Upstash Pay-as-you-go: ~$10/mês (100k comandos)

**Upgrade Render** (quando CPU > 80%):
- Standard: $25/mês (2GB RAM)

**Upgrade WhatsApp** (quando passar 900 conversas/mês):
- Meta Business: ~R$ 150/mês (10k conversas)

---

## 🔒 Segurança

### Checklist de Produção

- ✅ Trocar `AUTH_JWT_SECRET` (gerar aleatório de 64 caracteres)
- ✅ Trocar `AUTH_SEED_ADMIN_PASSWORD` (senha forte)
- ✅ Configurar `WA_WEBHOOK_SECRET` (validação de assinatura)
- ✅ Habilitar HTTPS (Render faz automaticamente)
- ✅ Não commitar `.env` no Git
- ✅ Rotacionar tokens a cada 90 dias
- ✅ Monitorar logs de acesso

### Backup

**Neon PostgreSQL:**
- Backups automáticos diários
- Retenção: 7 dias (free tier)
- Restore via dashboard

**Código:**
- GitHub como source of truth
- Tags de versão para releases

---

## 📈 Monitoramento

### Render Dashboard
- CPU, RAM, Network
- Logs em tempo real
- Alertas de erro

### Métricas Importantes
- Taxa de resposta do bot
- Tempo médio de resposta
- Conversas ativas/dia
- Taxa de conversão de leads

### Logs Estruturados
- Todos os eventos em JSON (structlog)
- Filtros por: `event`, `level`, `correlation_id`
- Exemplos:
  - `http_request_start`
  - `wa_message_received`
  - `lead.created`

---

## 🆘 Troubleshooting

### Problema: Webhook não recebe mensagens
**Solução:**
1. Verificar URL no Meta Business
2. Conferir `WA_VERIFY_TOKEN`
3. Checar logs no Render
4. Testar endpoint: `GET https://[url]/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=TOKEN&hub.challenge=123`

### Problema: Erro ao enviar mensagem
**Solução:**
1. Verificar `WA_TOKEN` válido
2. Confirmar `WA_PHONE_NUMBER_ID` correto
3. Checar limite de 1.000 conversas/mês
4. Verificar status do número no Meta Business

### Problema: Banco de dados lento
**Solução:**
1. Verificar uso de storage (Neon dashboard)
2. Analisar queries lentas (logs)
3. Considerar índices adicionais
4. Upgrade para Neon Pro se necessário

### Problema: Redis atingiu limite
**Solução:**
1. Verificar comandos/dia (Upstash dashboard)
2. Otimizar uso de cache
3. Reduzir TTL de sessões
4. Upgrade para Pay-as-you-go

---

## 📞 Suporte

### Documentação Oficial
- **Render**: https://render.com/docs
- **Neon**: https://neon.tech/docs
- **Upstash**: https://docs.upstash.com
- **WhatsApp API**: https://developers.facebook.com/docs/whatsapp

### Contatos de Emergência
- Render Status: https://status.render.com
- Neon Status: https://neonstatus.com
- Meta Business Support: https://business.facebook.com/help

---

## 🎯 Checklist Final

Antes de entregar ao cliente:

- [ ] Backend no ar e respondendo
- [ ] Frontend acessível
- [ ] Banco de dados criado e migrado
- [ ] Redis conectado
- [ ] Webhook WhatsApp configurado
- [ ] Teste de envio/recebimento de mensagem
- [ ] Admin user criado
- [ ] Cliente consegue fazer login
- [ ] Documentação de uso entregue
- [ ] Credenciais seguras compartilhadas

---

## 📅 Manutenção

### Mensal
- Verificar uso de recursos (DB, Redis)
- Revisar logs de erro
- Atualizar dependências críticas

### Trimestral
- Rotacionar tokens WhatsApp
- Backup manual do banco (além dos automáticos)
- Revisar custos e otimizar

### Anual
- Upgrade de versões (Python, PostgreSQL)
- Auditoria de segurança
- Revisão de arquitetura

---

---

## 🌐 Domínio Próprio (Opcional)

**Se o cliente quiser usar domínio customizado:**

### Custos
- Registro: R$ 40/ano (registro.br)
- Render Custom Domain: **GRÁTIS**
- SSL automático: **GRÁTIS** (Let's Encrypt)

### Configuração Rápida
1. Comprar domínio (ex: `atendeja.com.br`)
2. Configurar DNS (CNAME):
   ```
   api.atendeja.com.br → atendeja-api.onrender.com
   app.atendeja.com.br → atendeja-web.onrender.com
   ```
3. Adicionar domínios no Render Dashboard
4. Aguardar propagação DNS (até 24h)

---

**Última atualização**: 13/10/2025
**Versão**: 1.1
**Responsável**: Equipe AtendeJá
