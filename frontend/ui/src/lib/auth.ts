export function getToken(): string | null {
  try {
    return localStorage.getItem('auth_token')
  } catch {
    return null
  }
}

export function setToken(token: string) {
  try {
    localStorage.setItem('auth_token', token)
  } catch {
    // ignore
  }
}

export function clearToken() {
  try {
    localStorage.removeItem('auth_token')
  } catch {
    // ignore
  }
}

export function isAuthenticated(): boolean {
  const t = getToken()
  return !!t && t.length > 10
}

export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const url = input
  const headers = new Headers(init.headers || {})
  let sentBearer = false

  // Adiciona Authorization automaticamente para qualquer rota da API quando houver token
  if (url.startsWith('/api/') || url.startsWith('/admin/')) {
    const token = getToken()
    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
      sentBearer = true
    }

    try {
      const key = localStorage.getItem('ui_super_admin_key')
      if (key) headers.set('X-Super-Admin-Key', key)
    } catch {
      // ignore
    }

    try {
      const tid = localStorage.getItem('ui_tenant_id')
      if (tid && !headers.has('X-Tenant-Id')) headers.set('X-Tenant-Id', tid)
    } catch {
      // ignore
    }
  }

  if (url.startsWith('/super/')) {
    try {
      const key = localStorage.getItem('ui_super_admin_key')
      if (key) headers.set('X-Super-Admin-Key', key)
    } catch {
      // ignore
    }
  }

  const res = await fetch(url, { ...init, headers })

  if ((url.startsWith('/api/') || url.startsWith('/admin/')) && res.status === 401 && sentBearer) {
    try {
      clearToken()
      window.dispatchEvent(new Event('auth:invalid_token'))
    } catch {
      // ignore
    }
  }

  return res
}
