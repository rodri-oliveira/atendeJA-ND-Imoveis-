export function extractErrorMessage(js: unknown, fallback: string) {
  if (!js || typeof js !== 'object') return fallback
  const o = js as Record<string, unknown>
  const detail = o['detail']
  if (typeof detail === 'string' && detail) return detail
  const message = o['message']
  if (typeof message === 'string' && message) return message
  const err = o['error']
  if (err && typeof err === 'object') {
    const eo = err as Record<string, unknown>
    const em = eo['message']
    if (typeof em === 'string' && em) return em
    const code = eo['code']
    if (typeof code === 'string' && code) return code
  }
  return fallback
}

export function normalizeKey(s: string) {
  return (s || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '_')
    .replace(/[^a-z0-9_]/g, '')
}
