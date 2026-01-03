import React, { useEffect, useMemo, useState } from 'react'
import { apiFetch, isAuthenticated } from '../lib/auth'
import { Link, useNavigate } from 'react-router-dom'

type Role = 'admin' | 'collaborator'

type User = {
  id: number
  email: string
  full_name?: string | null
  role: Role
  is_active: boolean
}

type InviteOut = {
  token: string
  email: string
  role: Role
  expires_at: string
}

export default function UsersAdmin() {
  const [list, setList] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState<Role>('collaborator')
  const [creating, setCreating] = useState(false)
  const [filterRole, setFilterRole] = useState<string>('')
  const [filterActive, setFilterActive] = useState<string>('')
  const [lastInvite, setLastInvite] = useState<InviteOut | null>(null)
  const authed = isAuthenticated()
  const navigate = useNavigate()

  useEffect(() => {
    if (!authed) navigate('/login')
  }, [authed, navigate])

  const queryString = useMemo(() => {
    const p = new URLSearchParams()
    if (filterRole) p.set('role', filterRole)
    if (filterActive) p.set('is_active', filterActive)
    return p.toString()
  }, [filterRole, filterActive])

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch(`/api/admin/users${queryString ? `?${queryString}` : ''}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const js = await res.json()
      setList(js)
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'erro')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [queryString]) // eslint-disable-line react-hooks/exhaustive-deps

  async function onInvite(e: React.FormEvent) {
    e.preventDefault()
    setCreating(true)
    setError(null)
    try {
      const payload = { email, role, expires_hours: 72 }
      const res = await apiFetch('/api/admin/users/invite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try {
          const js = await res.json()
          msg = js?.detail || js?.message || msg
        } catch {
          /* ignore */
        }
        throw new Error(msg)
      }
      const js: InviteOut = await res.json()
      setLastInvite(js)
      setEmail(''); setFullName(''); setRole('collaborator')
      await load()
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao convidar usuário')
    } finally {
      setCreating(false)
    }
  }

  async function onToggleActive(u: User) {
    try {
      const res = await apiFetch(`/api/admin/users/${u.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !u.is_active }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await load()
    } catch (e) {
      console.warn(e)
    }
  }

  async function onPromote(u: User) {
    try {
      const res = await apiFetch(`/api/admin/users/${u.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: u.role === 'admin' ? 'collaborator' : 'admin' }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await load()
    } catch (e) {
      console.warn(e)
    }
  }


  async function onResendInvite(u: User) {
    try {
      const res = await apiFetch(`/api/admin/users/${u.id}/invite/resend`, { method: 'POST' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const js: InviteOut = await res.json()
      setLastInvite(js)
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao reenviar convite')
    }
  }

  async function onReset(u: User) {
    try {
      const res = await apiFetch(`/api/admin/users/${u.id}/reset`, { method: 'POST' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const js: InviteOut = await res.json()
      setLastInvite(js)
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao resetar senha')
    }
  }

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">Usuários</h1>
        <div className="text-sm text-slate-500">Gestão de usuários e perfis</div>
      </header>

      <div className="card space-y-4">
        <form onSubmit={onInvite} className="grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Email</label>
            <input className="input" type="email" value={email} onChange={e => setEmail(e.target.value)} required />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Nome</label>
            <input className="input" type="text" value={fullName} onChange={e => setFullName(e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Papel</label>
            <select className="select" value={role} onChange={e => setRole(e.target.value as Role)}>
              <option value="collaborator">Colaborador</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div className="flex items-center gap-2">
            <button disabled={creating} className="btn btn-primary">{creating ? 'Enviando...' : 'Convidar'}</button>
            <Link className="text-sm text-slate-600 underline hover:text-slate-800" to="/imoveis">Voltar</Link>
          </div>
        </form>
        {lastInvite && (
          <div className="text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-3">
            Convite gerado para <strong>{lastInvite.email}</strong> (papel: {lastInvite.role})<br />
            Token (use na tela de aceite): <code className="break-all">{lastInvite.token}</code><br />
            Expira em: {new Date(lastInvite.expires_at).toLocaleString()}
          </div>
        )}
      </div>

      <div className="card space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Filtrar papel</label>
            <select className="select" value={filterRole} onChange={e => setFilterRole(e.target.value)}>
              <option value="">Todos</option>
              <option value="admin">Admin</option>
              <option value="collaborator">Colaborador</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Ativo</label>
            <select className="select" value={filterActive} onChange={e => setFilterActive(e.target.value)}>
              <option value="">Todos</option>
              <option value="true">Ativos</option>
              <option value="false">Inativos</option>
            </select>
          </div>
        </div>

        {loading && <div className="text-sm text-slate-500">Carregando...</div>}
        {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">{error}</div>}

        {!loading && !error && (
          <div className="overflow-x-auto">
            <table className="table min-w-full text-sm">
              <thead>
                <tr className="text-left text-slate-600">
                  <th className="py-2 pr-3">ID</th>
                  <th className="py-2 pr-3">Email</th>
                  <th className="py-2 pr-3">Nome</th>
                  <th className="py-2 pr-3">Papel</th>
                  <th className="py-2 pr-3">Ativo</th>
                  <th className="py-2 pr-3">Ações</th>
                </tr>
              </thead>
              <tbody>
                {list.map(u => (
                  <tr key={u.id} className="table-row">
                    <td className="py-2 pr-3">{u.id}</td>
                    <td className="py-2 pr-3">{u.email}</td>
                    <td className="py-2 pr-3">{u.full_name || '-'}</td>
                    <td className="py-2 pr-3">
                      <span className={`badge ${u.role === 'admin' ? 'badge-success' : 'badge-neutral'}`}>{u.role}</span>
                    </td>
                    <td className="py-2 pr-3">{u.is_active ? 'Sim' : 'Não'}</td>
                    <td className="py-2 pr-3 flex gap-2">
                      <button onClick={() => onPromote(u)} className="btn btn-primary">{u.role === 'admin' ? 'Rebaixar' : 'Promover'}</button>
                      <button onClick={() => onToggleActive(u)} className={`btn ${u.is_active ? 'btn-warning' : 'btn-success'}`}>{u.is_active ? 'Desativar' : 'Ativar'}</button>
                      <button onClick={() => onResendInvite(u)} className="btn btn-secondary">Reenviar convite</button>
                      <button onClick={() => onReset(u)} className="btn btn-secondary">Resetar senha</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  )
}
