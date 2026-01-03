import React, { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import ErrorBoundary from '../components/ErrorBoundary'
import { isAuthenticated, clearToken } from '../lib/auth'
import { apiFetch } from '../lib/auth'
import { useUIConfig } from '../config/provider'

export default function AppShell() {
  const authed = isAuthenticated()
  const [me, setMe] = useState<{ email?: string; tenant_id?: number | null } | null>(null)
  const navigate = useNavigate()
  const cfg = useUIConfig()
  const [showSuper, setShowSuper] = useState(false)

  useEffect(() => {
    let alive = true
    async function loadMe() {
      try {
        if (!authed) { setMe(null); return }
        const res = await apiFetch('/api/auth/me')
        if (res.ok) {
          const js = await res.json()
          if (alive) setMe(js)
          try {
            const tid = (js as { tenant_id?: number | null })?.tenant_id
            if (typeof tid === 'number') localStorage.setItem('ui_tenant_id', String(tid))
          } catch {
            // ignore
          }
        } else {
          if (alive) setMe(null)
        }
      } catch {
        if (alive) setMe(null)
      }
    }
    loadMe()
    return () => { alive = false }
  }, [authed])

  useEffect(() => {
    try {
      setShowSuper(!!localStorage.getItem('ui_super_admin_key'))
    } catch {
      setShowSuper(false)
    }
  }, [cfg])

  function onLogout() {
    clearToken()
    setMe(null)
    navigate('/login')
  }
  return (
    <div className="min-h-screen flex bg-slate-50">
      <aside className="w-64 bg-gradient-to-b from-slate-800 to-slate-900 text-white flex-shrink-0 shadow-xl">
        <div className="px-6 py-5 border-b border-slate-700">
          <Link to="/" className="flex items-center space-x-3 hover:opacity-90 transition-opacity">
            <div className="w-8 h-8 bg-gradient-to-br from-primary-400 to-primary-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">ND</span>
            </div>
            <div>
              <div className="text-lg font-bold">AtendeJá</div>
              <div className="text-xs text-slate-300">{cfg?.branding?.tenantName || 'Tenant'}</div>
            </div>
          </Link>
        </div>
        <nav className="p-4 space-y-2">
          <div className="px-3 py-2 text-xs uppercase tracking-wide text-slate-400 font-semibold">Imobiliário</div>
          <Item to="/imoveis" label="Imóveis" />
          <Item to="/import" label="Importar CSV" />
          <Item to="/leads" label="Leads" />
          <Item to="/ops" label="Operações" />
          <Item to="/reports" label="Relatórios" />
          {authed && (
            <>
              <NavLink
                to="/users"
                className="block px-3 py-2 text-xs uppercase tracking-wide font-semibold text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg"
              >
                Admin
              </NavLink>
              <Item to="/users" label="Usuários" />
              {showSuper && <Item to="/super/tenants" label="Tenants" />}
            </>
          )}
          <Item to="/sobre" label="Sobre" />
        </nav>
      </aside>
      <main className="flex-1 bg-slate-50">
        <div className="p-4 flex items-center justify-end gap-3">
          {authed && (
            <div className="flex items-center gap-3">
              <div className="px-3 py-1 rounded-full bg-slate-200 text-slate-800 text-xs font-medium">
                {me?.email || 'logado'}
              </div>
              <button onClick={onLogout} className="text-xs px-3 py-1 rounded-lg bg-slate-800 text-white hover:bg-slate-700">Sair</button>
            </div>
          )}
        </div>
        <div className="p-6 pt-0">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </div>
      </main>
    </div>
  )
}

function Item({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }: { isActive: boolean }) =>
        `group flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 ${
          isActive
            ? 'bg-primary-600 text-white shadow-lg shadow-primary-600/25'
            : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
        }`
      }
    >
      {({ isActive }: { isActive: boolean }) => (
        <>
          <span className="truncate">{label}</span>
          {/* Indicador visual para item ativo */}
          <div
            className={`ml-auto w-1 h-4 rounded-full transition-opacity ${
              isActive ? 'opacity-100 bg-primary-300' : 'opacity-0'
            }`}
          />
        </>
      )}
    </NavLink>
  )
}
