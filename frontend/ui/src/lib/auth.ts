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

  // Adiciona Authorization automaticamente para qualquer rota da API quando houver token
  if (url.startsWith('/api/') || url.startsWith('/admin/')) {
    const token = getToken()
    if (token) headers.set('Authorization', `Bearer ${token}`)

    try {
      const tid = localStorage.getItem('ui_tenant_id')
      if (tid) headers.set('X-Tenant-Id', tid)
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

  return fetch(url, { ...init, headers })
}
