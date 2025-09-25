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
const { Client, LocalAuth } = require('whatsapp-web.js')

require('dotenv').config({ path: path.resolve(__dirname, '.env') })

// Configurações via env
const MCP_URL = process.env.MCP_URL || 'http://localhost:8000/mcp/execute'
const MCP_TOKEN = process.env.MCP_TOKEN || ''
const MCP_TENANT_ID = process.env.MCP_TENANT_ID || 'default'
const WA_SESSION_NAME = process.env.WA_SESSION_NAME || 'atendeja-wa'
const WA_QR_FILE = process.env.WA_QR_FILE || path.resolve(__dirname, 'qr.png')
const RATE_S = parseInt(process.env.WA_RATE_LIMIT_PER_CONTACT_SECONDS || '2', 10)

// Rate limit simples em memória
const lastByContact = new Map() // wa_id -> timestamp (ms)
function allowContact(wa_id) {
  const now = Date.now()
  const last = lastByContact.get(wa_id) || 0
  if (now - last < RATE_S * 1000) return false
  lastByContact.set(wa_id, now)
  return true
}

// Cliente WhatsApp com sessão persistente (sem abrir navegador visível)
const client = new Client({
  authStrategy: new LocalAuth({ clientId: WA_SESSION_NAME }),
  puppeteer: {
    headless: true,
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
})

client.on('disconnected', (reason) => {
  console.warn('[wa] Desconectado:', reason)
})

// Encaminha mensagem para MCP
async function sendToMCP(text) {
  const body = {
    input: String(text || ''),
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

client.on('message_create', async (msg) => {
  try {
    // Tratar mensagens enviadas por você mesmo (auto-teste)
    if (msg.fromMe) {
      if (!allowContact(msg.to)) return
      if (msg.to.endsWith('@g.us')) return // ignora grupos
      const mcp = await sendToMCP(msg.body || '')
      const reply = mcp?.message || 'Ok.'
      await client.sendMessage(msg.to, reply)
      return
    }

    // Mensagens recebidas de contatos
    const chatId = msg.from
    if (chatId.endsWith('@g.us')) return // ignora grupos
    // Rate limit por contato
    if (!allowContact(chatId)) return

    const text = msg.body || ''
    const mcp = await sendToMCP(text)
    const reply = mcp?.message || 'Ok.'
    await client.sendMessage(chatId, reply)
  } catch (e) {
    console.error('[wa] Erro ao processar mensagem:', e.message)
    try {
      const to = msg.fromMe ? msg.to : msg.from
      await client.sendMessage(to, '⚠️ Ocorreu um erro ao processar. Tente novamente em instantes.')
    } catch {}
  }
})

async function main() {
  console.log('[wa] Iniciando adapter WA...')
  console.log('[wa] MCP_URL:', MCP_URL)
  await client.initialize()
}

main().catch((e) => {
  console.error('[wa] Falha geral:', e)
  process.exit(1)
})
