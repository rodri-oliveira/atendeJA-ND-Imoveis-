/*
  Adapter WA (whatsapp-web.js) – POC segura para desenvolvimento local
  - Conecta no WhatsApp Web com sessão persistida (LocalAuth)
  - Salva QR em arquivo PNG
  - Rate limit por contato (env WA_RATE_LIMIT_PER_CONTACT_SECONDS)
  - Encaminha mensagens para o MCP do backend (/mcp/execute)
  - Ignora grupos por padrão
*/

const fs = require('fs')
const path = require('path')
const qrcode = require('qrcode')
const fetch = require('node-fetch')
const puppeteer = require('puppeteer')
const { Client, LocalAuth } = require('whatsapp-web.js')

require('dotenv').config({ path: path.resolve(__dirname, '.env') })

// Configurações via env
const MCP_URL = process.env.MCP_URL || 'http://localhost:8000/api/v1/mcp/execute'
const MCP_TOKEN = process.env.MCP_TOKEN || ''
const MCP_TENANT_ID = process.env.MCP_TENANT_ID || 'default'
const WA_SESSION_NAME = process.env.WA_SESSION_NAME || 'atendeja-wa'
const WA_QR_FILE = process.env.WA_QR_FILE || path.resolve(__dirname, 'qr.png')
const RATE_S = parseInt(process.env.WA_RATE_LIMIT_PER_CONTACT_SECONDS || '2', 10)
const OUTBOUND_ENABLED = String(process.env.WA_OUTBOUND_ENABLED || 'false').toLowerCase() === 'true'
// Permitir auto-teste (processar mensagens fromMe)
const ALLOW_FROM_ME = String(process.env.WA_ALLOW_FROM_ME || 'false').toLowerCase() === 'true'
const CLEAR_ON_START = String(process.env.WA_CLEAR_STATE_ON_START || 'false').toLowerCase() === 'true'
// Whitelist opcional de contatos permitidos (se vazio, atende todos)
const ONLY_CONTACTS = String(process.env.WA_ONLY_CONTACTS || '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean)
const allowedJids = new Set(
  ONLY_CONTACTS.map((n) => {
    if (n.includes('@')) return n.toLowerCase()
    const digits = n.replace(/\D/g, '')
    return `${digits}@c.us`
  })
)
// Guard contra reprocessamento de mensagens antigas ao iniciar
const START_TIME_MS = Date.now()

// Rate limit simples em memória
const lastByContact = new Map() // wa_id -> timestamp (ms)
function allowContact(wa_id) {
  const now = Date.now()
  const last = lastByContact.get(wa_id) || 0
  if (now - last < RATE_S * 1000) return false
  lastByContact.set(wa_id, now)
  return true
}

// Anti-eco: rastreia a última mensagem enviada pelo bot por chat
const lastBotByChat = new Map() // chatId -> { body, ts }
const ANTI_ECHO_WINDOW_MS = parseInt(process.env.WA_ANTI_ECHO_WINDOW_MS || '30000', 10)

// Cliente WhatsApp com sessão persistente (sem abrir navegador visível)
// Detecta caminho do navegador (Chromium baixado pelo Puppeteer ou Chrome local)
let executablePath
try {
  executablePath = puppeteer.executablePath()
} catch {}
if (!executablePath) {
  const winChrome = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
  if (fs.existsSync(winChrome)) executablePath = winChrome
}

const client = new Client({
  authStrategy: new LocalAuth({ clientId: WA_SESSION_NAME }),
  puppeteer: {
    headless: true, // maior compatibilidade em Windows
    executablePath,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
    ],
  },
})

client.on('qr', async (qr) => {
  console.log('[wa] QR recebido. Gerando PNG em:', WA_QR_FILE)
  try {
    await qrcode.toFile(WA_QR_FILE, qr)
    console.log('[wa] Abra o arquivo para escanear:', WA_QR_FILE)
  } catch (e) {
    console.error('[wa] Falha ao salvar QR:', e)
  }
})

client.on('ready', () => {
  console.log('[wa] Cliente pronto (ready).')
  if (allowedJids.size > 0) {
    console.log('[wa] Whitelist ativa (WA_ONLY_CONTACTS):', Array.from(allowedJids).join(', '))
  } else {
    console.log('[wa] Whitelist desativada: atendendo todos os contatos (somente DEV).')
  }
  if (ALLOW_FROM_ME) {
    console.log('[wa] ⚠️  Auto-teste habilitado (WA_ALLOW_FROM_ME=true): processará mensagens fromMe')
  }
  // DEV: limpar estado no backend para contatos da whitelist
  if (CLEAR_ON_START && allowedJids.size > 0) {
    (async () => {
      try {
        const url = MCP_URL.replace(/\/execute$/, '/admin/state/clear')
        const sender_ids = Array.from(allowedJids)
        const headers = { 'Content-Type': 'application/json' }
        if (MCP_TOKEN) headers['Authorization'] = `Bearer ${MCP_TOKEN}`
        console.log('[wa] 🧹 URL de limpeza:', url)
        console.log('[wa] 🧹 Limpando estado no backend para:', sender_ids.join(', '))
        const res = await fetch(url, { method: 'POST', headers, body: JSON.stringify({ sender_ids }) })
        const js = await res.json().catch(() => ({}))
        console.log('[wa] 🧹 Resultado limpeza:', res.status, js)
      } catch (e) {
        console.warn('[wa] ⚠️ Falha ao limpar estado no backend:', e.message)
      }
    })()
  }
})

client.on('disconnected', (reason) => {
  console.warn('[wa] Desconectado:', reason)
})

// Encaminha mensagem para MCP
async function sendToMCP(text, senderId) {
  const body = {
    input: String(text || ''),
    sender_id: String(senderId || 'unknown'),
    tenant_id: MCP_TENANT_ID,
    mode: 'auto',
  }
  const headers = { 'Content-Type': 'application/json' }
  if (MCP_TOKEN) headers['Authorization'] = `Bearer ${MCP_TOKEN}`
  const res = await fetch(MCP_URL, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const t = await res.text().catch(() => '')
    throw new Error(`MCP ${res.status} ${t}`)
  }
  return res.json()
}

// Handler unificado para processar mensagens
async function handleMessage(msg, source) {
  try {
    console.log(`[wa] ===== MENSAGEM RECEBIDA (${source}) =====`)
    console.log('[wa] fromMe:', msg.fromMe)
    console.log('[wa] from:', msg.from)
    console.log('[wa] to:', msg.to)
    console.log('[wa] type:', msg.type)
    console.log('[wa] body:', msg.body)
    console.log('[wa] timestamp:', msg.timestamp, '→', new Date(msg.timestamp * 1000).toISOString())

    // Mensagens enviadas por este cliente (fromMe)
    if (msg.fromMe) {
      if (!ALLOW_FROM_ME) {
        console.log('[wa] ❌ Ignorando: fromMe=true (auto-teste desabilitado)')
        return
      }
      // Auto-teste habilitado: processar como se fosse mensagem para o destinatário
      console.log('[wa] 🔄 Processando fromMe (auto-teste): destinatário =', msg.to)
      const chatId = msg.to
      
      // Ignorar grupos
      if (chatId.endsWith('@g.us')) {
        console.log('[wa] ❌ Ignorando fromMe: grupo')
        return
      }
      
      // Whitelist (se configurada)
      // Permitir bypass quando o próprio remetente (msg.from) consta na whitelist (facilita auto-teste)
      const whitelistBypassFromMe = allowedJids.size > 0 && allowedJids.has(msg.from)
      if (allowedJids.size > 0 && !allowedJids.has(chatId) && !whitelistBypassFromMe) {
        console.log('[wa] ❌ Ignorando fromMe: destinatário fora da whitelist →', chatId)
        return
      }
      if (whitelistBypassFromMe && !allowedJids.has(chatId)) {
        console.log('[wa] ✅ Whitelist bypass (fromMe): remetente autorizado na whitelist →', msg.from)
      }
      
      // Ignorar tipos que não são chat de texto
      if (msg.type && msg.type !== 'chat') {
        console.log('[wa] ❌ Ignorando fromMe: tipo não suportado →', msg.type)
        return
      }
      
      // Ignorar mensagens antigas
      const tsMs = msg.timestamp ? Number(msg.timestamp) * 1000 : Date.now()
      if (tsMs < (START_TIME_MS - 10000)) {
        console.log('[wa] ❌ Ignorando fromMe: mensagem antiga de', new Date(tsMs).toISOString())
        return
      }
      
      const text = (msg.body || '').trim()
      if (!text) {
        console.log('[wa] ❌ Ignorando fromMe: corpo vazio')
        return
      }

      // Anti-eco: ignorar mensagem que é igual à última resposta enviada pelo bot recentemente
      const last = lastBotByChat.get(chatId)
      if (last) {
        const textNorm = text.trim().toLowerCase().replace(/\s+/g, ' ')
        const lastNorm = last.body.trim().toLowerCase().replace(/\s+/g, ' ')
        const elapsed = Date.now() - last.ts
        if (textNorm === lastNorm && elapsed < ANTI_ECHO_WINDOW_MS) {
          console.log('[wa] ❌ Ignorando fromMe: eco da própria mensagem do bot (elapsed:', elapsed, 'ms)')
          return
        }
      }
      
      // Rate limit
      if (!allowContact(chatId)) {
        console.log('[wa] ❌ Rate limit atingido (fromMe) para', chatId)
        return
      }
      
      console.log('[wa] ✅ Processando fromMe para:', chatId)
      const mcp = await sendToMCP(text, chatId)
      const reply = mcp?.message || 'Ok.'
      
      console.log('[wa] 📤 Enviando resposta (fromMe) para:', chatId)
      console.log('[wa] 📝 Resposta:', reply)
      
      if (OUTBOUND_ENABLED) {
        // Registrar ANTES de enviar para evitar race condition
        lastBotByChat.set(chatId, { body: reply, ts: Date.now() })
        await client.sendMessage(chatId, reply)
        console.log('[wa] ✅ Resposta enviada (fromMe) com sucesso')
      } else {
        console.log('[wa] OUTBOUND desabilitado: não enviando resposta (fromMe).')
      }
      return
    }

    const chatId = msg.from
    if (chatId.endsWith('@g.us')) {
      console.log('[wa] ❌ Ignorando: grupo')
      return
    }

    // Whitelist (se configurada)
    if (allowedJids.size > 0 && !allowedJids.has(chatId)) {
      console.log('[wa] ❌ Ignorando: contato fora da whitelist →', chatId)
      return
    }

    // Ignorar tipos que não são chat de texto
    if (msg.type && msg.type !== 'chat') {
      console.log('[wa] ❌ Ignorando: tipo não suportado →', msg.type)
      return
    }

    // Ignorar mensagens antigas carregadas no startup
    const tsMs = msg.timestamp ? Number(msg.timestamp) * 1000 : Date.now()
    if (tsMs < (START_TIME_MS - 10000)) {
      console.log('[wa] ❌ Ignorando mensagem antiga de', chatId, 'ts=', new Date(tsMs).toISOString())
      return
    }

    const text = (msg.body || '').trim()
    if (!text) {
      console.log('[wa] ❌ Ignorando: corpo vazio após trim')
      return
    }

    // Rate limit por contato
    if (!allowContact(chatId)) return

    const mcp = await sendToMCP(text, chatId)
    const reply = mcp?.message || 'Ok.'
    if (OUTBOUND_ENABLED) {
      // Registrar ANTES de enviar para evitar race condition
      lastBotByChat.set(chatId, { body: reply, ts: Date.now() })
      await client.sendMessage(chatId, reply)
    } else {
      console.log('[wa] OUTBOUND desabilitado: não enviando resposta (inbound).')
    }
  } catch (e) {
    console.error('[wa] Erro ao processar mensagem:', e.message)
    try {
      const to = msg.fromMe ? msg.to : msg.from
      if (OUTBOUND_ENABLED) {
        await client.sendMessage(to, '⚠️ Ocorreu um erro ao processar. Tente novamente em instantes.')
      } else {
        console.log('[wa] OUTBOUND desabilitado: erro suprimido sem resposta.')
      }
    } catch {}
  }
}

// Registrar listeners para ambos os eventos
client.on('message', (msg) => handleMessage(msg, 'message'))
client.on('message_create', (msg) => handleMessage(msg, 'message_create'))

async function main() {
  console.log('[wa] Iniciando adapter WA...')
  console.log('[wa] MCP_URL:', MCP_URL)
  await client.initialize()
}

main().catch((e) => {
  console.error('[wa] Falha geral:', e)
  process.exit(1)
})
