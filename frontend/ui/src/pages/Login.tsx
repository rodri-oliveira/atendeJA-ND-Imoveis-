import React, { useState } from 'react'
import { useNavigate, Link, useLocation, useSearchParams } from 'react-router-dom'
import { setToken, clearToken } from '../lib/auth'

type LoginLocationState = {
  redirectTo?: string
}

export default function Login() {
  const [search] = useSearchParams()
  const [email, setEmail] = useState(() => search.get('email') || 'admin@example.com')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const location = useLocation()

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      setLoading(true)
      const form = new URLSearchParams()
      form.set('username', email)
      form.set('password', password)
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: form.toString(),
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
      const js = await res.json()
      const token = js?.access_token
      if (!token) throw new Error('token ausente na resposta')
      setToken(token)
      const state = (location.state || {}) as LoginLocationState
      const dest = state.redirectTo || '/imoveis'
      navigate(dest, { replace: true })
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Falha no login')
    } finally {
      setLoading(false)
    }
  }

  function onLogout() {
    clearToken()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <div className="w-full max-w-md bg-white rounded-xl shadow-card border border-slate-200 p-6 space-y-5">
        <h1 className="text-2xl font-bold text-slate-800">Entrar</h1>
        {error && (
          <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">{error}</div>
        )}
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full rounded-lg border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="admin@example.com"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Senha</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full rounded-lg border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="SuaSenhaForte123"
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full px-4 py-2.5 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50"
          >
            {loading ? 'Entrando...' : 'Entrar'}
          </button>
        </form>
        <div className="text-xs text-slate-500">
          Dica: use <code>admin@example.com</code> com a senha definida no backend (.env).
        </div>
        <div className="text-sm text-slate-600">
          <Link to="/imoveis" className="underline">Voltar</Link>
          <button onClick={onLogout} className="ml-3 underline">Sair</button>
        </div>
      </div>
    </div>
  )
}
