import React, { useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { apiFetch } from '../lib/auth'

export default function AcceptInvite() {
  const [search] = useSearchParams()
  const [tokenParam] = useState(() => search.get('token') || '')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const navigate = useNavigate()

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setSuccess(null)
    try {
      const res = await apiFetch('/api/auth/accept_invite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: tokenParam, password, full_name: fullName || undefined }),
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
      const out = (await res.json()) as { email?: string }
      setSuccess('Convite aceito com sucesso. Você já pode fazer login.')
      // Redireciona para login após breve intervalo
      setTimeout(() => {
        const email = (out?.email || '').trim()
        if (email) navigate(`/login?email=${encodeURIComponent(email)}`)
        else navigate('/login')
      }, 1200)
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao aceitar convite')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md bg-white border border-slate-200 rounded-2xl shadow-sm p-6 space-y-4">
        <h1 className="text-2xl font-bold text-slate-800">Aceitar convite</h1>
        <p className="text-sm text-slate-600">Defina sua senha para ativar o acesso.</p>

        {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">{error}</div>}
        {success && <div className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg p-3">{success}</div>}

        <form className="space-y-3" onSubmit={onSubmit}>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Token</label>
            <input
              name="token"
              autoComplete="off"
              className="input"
              value={tokenParam}
              disabled
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Nome</label>
            <input
              name="full_name"
              autoComplete="off"
              className="input"
              value={fullName}
              onChange={e => setFullName(e.target.value)}
              placeholder="Seu nome (opcional)"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Senha</label>
            <input
              name="new_password"
              autoComplete="new-password"
              className="input"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              minLength={8}
              placeholder="Crie uma senha"
            />
          </div>
          <button type="submit" className="btn btn-primary w-full" disabled={loading}>
            {loading ? 'Ativando...' : 'Ativar acesso'}
          </button>
        </form>

        <div className="text-xs text-slate-500">
          Já tem conta? <button className="text-indigo-600 underline" onClick={() => navigate('/login')}>Ir para login</button>
        </div>
      </div>
    </div>
  )
}
