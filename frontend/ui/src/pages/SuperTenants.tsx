import React, { useEffect, useMemo, useState } from 'react'
import { apiFetch, isAuthenticated } from '../lib/auth'
import { useNavigate } from 'react-router-dom'

type Tenant = {
  id: number
  name: string
  timezone: string
  is_active: boolean
}

type WhatsAppAccount = {
  id: number
  tenant_id: number
  phone_number_id: string
  waba_id?: string | null
  is_active: boolean
}

type InviteAdminOut = {
  token: string
  email: string
  tenant_id: number
  role: string
}

type AssignUserOut = {
  user_id: number
  email: string
  tenant_id: number
}

export default function SuperTenants() {
  const authed = isAuthenticated()
  const navigate = useNavigate()

  const [tenants, setTenants] = useState<Tenant[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [timezone, setTimezone] = useState('America/Sao_Paulo')
  const [creating, setCreating] = useState(false)

  const [selectedTenantId, setSelectedTenantId] = useState<number | null>(null)
  const selectedTenant = useMemo(
    () => tenants.find(t => t.id === selectedTenantId) || null,
    [tenants, selectedTenantId]
  )

  async function setTenantActive(tid: number, next: boolean) {
    setError(null)
    try {
      const res = await apiFetch(`/super/tenants/${tid}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: next }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await loadTenants()
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao atualizar tenant')
    }

  }

  async function onAssignUser(e: React.FormEvent) {
    e.preventDefault()
    if (selectedTenantId == null) return
    setAssigning(true)
    setError(null)
    try {
      const res = await apiFetch(`/super/tenants/${selectedTenantId}/assign-user`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: assignEmail }),
      })
      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try {
          const js = await res.json()
          msg = js?.detail || js?.message || msg
        } catch {
          // ignore
        }
        throw new Error(msg)
      }
      const js = (await res.json()) as AssignUserOut
      setLastAssign(js)
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao atribuir usuário')
    } finally {
      setAssigning(false)
    }
  }

  const [waAccounts, setWaAccounts] = useState<WhatsAppAccount[]>([])
  const [waLoading, setWaLoading] = useState(false)

  const [waPhoneNumberId, setWaPhoneNumberId] = useState('')
  const [waToken, setWaToken] = useState('')
  const [waWabaId, setWaWabaId] = useState('')
  const [waCreating, setWaCreating] = useState(false)

  const [inviteEmail, setInviteEmail] = useState('')
  const [inviting, setInviting] = useState(false)
  const [lastInvite, setLastInvite] = useState<InviteAdminOut | null>(null)

  const [assignEmail, setAssignEmail] = useState('')
  const [assigning, setAssigning] = useState(false)
  const [lastAssign, setLastAssign] = useState<AssignUserOut | null>(null)

  useEffect(() => {
    if (!authed) navigate('/login')
  }, [authed, navigate])

  async function loadTenants() {
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch('/super/tenants')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const js = (await res.json()) as Tenant[]
      setTenants(js)
      if (js.length > 0 && selectedTenantId == null) setSelectedTenantId(js[0]!.id)
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao carregar tenants')
    } finally {
      setLoading(false)
    }
  }

  async function loadWhatsAppAccounts(tid: number) {
    setWaLoading(true)
    try {
      const res = await apiFetch(`/super/tenants/${tid}/whatsapp-accounts`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const js = (await res.json()) as WhatsAppAccount[]
      setWaAccounts(js)
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao carregar whatsapp accounts')
    } finally {
      setWaLoading(false)
    }
  }

  useEffect(() => {
    loadTenants()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (selectedTenantId != null) loadWhatsAppAccounts(selectedTenantId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTenantId])

  async function onCreateTenant(e: React.FormEvent) {
    e.preventDefault()
    setCreating(true)
    setError(null)
    try {
      const res = await apiFetch('/super/tenants', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, timezone }),
      })
      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try {
          const js = await res.json()
          msg = js?.detail || js?.message || msg
        } catch {
          // ignore
        }
        throw new Error(msg)
      }
      setName('')
      setTimezone('America/Sao_Paulo')
      await loadTenants()
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao criar tenant')
    } finally {
      setCreating(false)
    }
  }

  async function onCreateWhatsAppAccount(e: React.FormEvent) {
    e.preventDefault()
    if (selectedTenantId == null) return
    setWaCreating(true)
    setError(null)
    try {
      const res = await apiFetch(`/super/tenants/${selectedTenantId}/whatsapp-accounts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone_number_id: waPhoneNumberId,
          token: waToken || undefined,
          waba_id: waWabaId || undefined,
          is_active: true,
        }),
      })
      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try {
          const js = await res.json()
          msg = js?.detail || js?.message || msg
        } catch {
          // ignore
        }
        throw new Error(msg)
      }
      setWaPhoneNumberId('')
      setWaToken('')
      setWaWabaId('')
      await loadWhatsAppAccounts(selectedTenantId)
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao criar whatsapp account')
    } finally {
      setWaCreating(false)
    }
  }

  async function onInviteAdmin(e: React.FormEvent) {
    e.preventDefault()
    if (selectedTenantId == null) return
    setInviting(true)
    setError(null)
    try {
      const res = await apiFetch(`/super/tenants/${selectedTenantId}/invite-admin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: inviteEmail, expires_hours: 72 }),
      })
      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try {
          const js = await res.json()
          msg = js?.detail || js?.message || msg
        } catch {
          // ignore
        }
        throw new Error(msg)
      }
      const js = (await res.json()) as InviteAdminOut
      setLastInvite(js)
      setInviteEmail('')
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao convidar admin')
    } finally {
      setInviting(false)
    }
  }

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">Tenants (Super Admin)</h1>
        <div className="text-sm text-slate-500">Onboarding e credenciais WhatsApp</div>
      </header>

      {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card space-y-4">
          <div className="card-header">Criar tenant</div>
          <form className="space-y-3" onSubmit={onCreateTenant}>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Nome</label>
              <input className="input" value={name} onChange={e => setName(e.target.value)} required />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Timezone</label>
              <input className="input" value={timezone} onChange={e => setTimezone(e.target.value)} />
            </div>
            <button className="btn btn-primary w-full" disabled={creating}>
              {creating ? 'Criando...' : 'Criar'}
            </button>
          </form>
        </div>

        <div className="card space-y-3 lg:col-span-2">
          <div className="flex items-center justify-between">
            <div className="card-header">Tenants</div>
            <button className="btn btn-ghost" onClick={loadTenants} disabled={loading}>Atualizar</button>
          </div>

          {loading ? (
            <div className="text-sm text-slate-500">Carregando...</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {tenants.map(t => (
                <button
                  key={t.id}
                  onClick={() => setSelectedTenantId(t.id)}
                  className={`text-left rounded-xl border p-4 transition-all-smooth ${
                    selectedTenantId === t.id ? 'border-primary-400 bg-primary-50' : 'border-slate-200 bg-white hover:bg-slate-50'
                  }`}
                >
                  <div className="text-sm font-semibold text-slate-800">{t.name}</div>
                  <div className="text-xs text-slate-500">#{t.id} • {t.timezone}</div>
                  <div className="mt-2">
                    <span className={`badge ${t.is_active ? 'badge-success' : 'badge-warning'}`}>
                      {t.is_active ? 'Ativo' : 'Suspenso'}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}

          <div className="border-t border-slate-200 pt-4" />

          <div className="card-header">Atribuir usuário existente ao tenant</div>
          <form className="space-y-3" onSubmit={onAssignUser}>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
              <input className="input" type="email" value={assignEmail} onChange={e => setAssignEmail(e.target.value)} required />
            </div>
            <button className="btn btn-ghost w-full" disabled={assigning || selectedTenantId == null}>
              {assigning ? 'Atribuindo...' : 'Atribuir ao tenant selecionado'}
            </button>
          </form>

          {lastAssign && (
            <div className="text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-3">
              Usuário <strong>{lastAssign.email}</strong> agora está no tenant <strong>#{lastAssign.tenant_id}</strong>.<br />
              <span className="text-xs text-slate-500">Dica: faça logout/login para o painel carregar o tenant correto.</span>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card space-y-4 lg:col-span-2">
          <div className="flex items-center justify-between">
            <div className="card-header">WhatsApp Accounts</div>
            {selectedTenant && <div className="text-xs text-slate-500">Tenant: {selectedTenant.name} (#{selectedTenant.id})</div>}
          </div>

          {selectedTenant && (
            <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div className="text-sm text-slate-700">
                Status do tenant: <strong>{selectedTenant.is_active ? 'Ativo' : 'Suspenso'}</strong>
              </div>
              <button
                className={`btn ${selectedTenant.is_active ? 'btn-warning' : 'btn-success'}`}
                onClick={() => {
                  const action = selectedTenant.is_active ? 'suspender' : 'reativar';
                  if (window.confirm(`Tem certeza que deseja ${action} o acesso para o tenant "${selectedTenant.name}"?`)) {
                    setTenantActive(selectedTenant.id, !selectedTenant.is_active)
                  }
                }}
              >
                {selectedTenant.is_active ? 'Suspender acesso' : 'Reativar acesso'}
              </button>
            </div>
          )}

          {waLoading ? (
            <div className="text-sm text-slate-500">Carregando...</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="table min-w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-600">
                    <th className="py-2 pr-3">ID</th>
                    <th className="py-2 pr-3">phone_number_id</th>
                    <th className="py-2 pr-3">waba_id</th>
                    <th className="py-2 pr-3">Ativo</th>
                  </tr>
                </thead>
                <tbody>
                  {waAccounts.map(a => (
                    <tr key={a.id} className="table-row">
                      <td className="py-2 pr-3">{a.id}</td>
                      <td className="py-2 pr-3 font-mono text-xs">{a.phone_number_id}</td>
                      <td className="py-2 pr-3 font-mono text-xs">{a.waba_id || '-'}</td>
                      <td className="py-2 pr-3">{a.is_active ? 'Sim' : 'Não'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!waAccounts.length && <div className="text-sm text-slate-500 mt-3">Nenhuma conta cadastrada.</div>}
            </div>
          )}

          <form className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end" onSubmit={onCreateWhatsAppAccount}>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-1">phone_number_id</label>
              <input className="input" value={waPhoneNumberId} onChange={e => setWaPhoneNumberId(e.target.value)} required />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">waba_id</label>
              <input className="input" value={waWabaId} onChange={e => setWaWabaId(e.target.value)} />
            </div>
            <div>
              <button className="btn btn-primary w-full" disabled={waCreating || selectedTenantId == null}>
                {waCreating ? 'Salvando...' : 'Adicionar'}
              </button>
            </div>
            <div className="md:col-span-4">
              <label className="block text-sm font-medium text-slate-700 mb-1">Token (opcional)</label>
              <input className="input" value={waToken} onChange={e => setWaToken(e.target.value)} placeholder="Armazene com cuidado (produção: use secret manager)" />
            </div>
          </form>
        </div>

        <div className="card space-y-4">
          <div className="card-header">Atribuir usuário existente ao tenant</div>
          <form className="space-y-3" onSubmit={onAssignUser}>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
              <input className="input" type="email" value={assignEmail} onChange={e => setAssignEmail(e.target.value)} required placeholder="email@exemplo.com" />
            </div>
            <button className="btn btn-ghost w-full" disabled={assigning || selectedTenantId == null}>
              {assigning ? 'Atribuindo...' : 'Atribuir ao tenant selecionado'}
            </button>
          </form>
          {lastAssign && (
            <div className="text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-3">
              Usuário <strong>{lastAssign.email}</strong> agora está no tenant <strong>#{lastAssign.tenant_id}</strong>.<br />
              <span className="text-xs text-slate-500">Dica: faça logout/login para o painel carregar o tenant correto.</span>
            </div>
          )}
          <div className="border-t border-slate-200 my-4" />
          <div className="card-header">Convidar admin do tenant</div>
          <form className="space-y-3" onSubmit={onInviteAdmin}>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
              <input className="input" type="email" value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} required />
            </div>
            <button className="btn btn-primary w-full" disabled={inviting || selectedTenantId == null}>
              {inviting ? 'Gerando...' : 'Gerar convite'}
            </button>
          </form>

          {lastInvite && (
            <div className="text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-3">
              Token gerado para <strong>{lastInvite.email}</strong><br />
              <div className="mt-2">
                <div className="text-xs text-slate-500">Link:</div>
                <code className="break-all">/accept-invite?token={lastInvite.token}</code>
              </div>
              <div className="mt-2">
                <div className="text-xs text-slate-500">Token:</div>
                <code className="break-all">{lastInvite.token}</code>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
