import React, { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import ErrorBoundary from '../components/ErrorBoundary'
import { isAuthenticated, clearToken } from '../lib/auth'
import { apiFetch } from '../lib/auth'
import { useUIConfig } from '../config/provider'
import { useTenant } from '../contexts/TenantContext'

export default function AppShell() {
  const authed = isAuthenticated()
  const { tenantId } = useTenant()
  const [me, setMe] = useState<{ email?: string; tenant_id?: number | null; role?: string; tenant_name?: string | null } | null>(null)
  const [tenantDomain, setTenantDomain] = useState<string>('real_estate')
  const [activeTenantName, setActiveTenantName] = useState<string | null>(null)
  const navigate = useNavigate()
  const cfg = useUIConfig()
  const [showSuper, setShowSuper] = useState(false)
  const [catalogOpen, setCatalogOpen] = useState(false)
  const [adminOpen, setAdminOpen] = useState(false)

  useEffect(() => {
    function onInvalidToken() {
      setMe(null)
      navigate('/login', { replace: true })
    }

    window.addEventListener('auth:invalid_token', onInvalidToken)
    return () => window.removeEventListener('auth:invalid_token', onInvalidToken)
  }, [navigate])

  useEffect(() => {
    let alive = true
    async function loadMe() {
      try {
        if (!authed) { setMe(null); return }
        const res = await apiFetch('/api/auth/me')
        if (res.ok) {
          const js = await res.json()
          if (alive) setMe(js)
        } else {
          if (alive) setMe(null)
        }
      } catch {
        if (alive) setMe(null)
      }
    }
    loadMe()
    return () => { alive = false }
  }, [authed, tenantId])

  useEffect(() => {
    let alive = true
    async function loadDomain() {
      try {
        if (!authed) {
          if (alive) setTenantDomain('real_estate')
          return
        }
        const res = await apiFetch('/api/ui/domain', { cache: 'no-store' })
        if (!res.ok) {
          if (alive) setTenantDomain('real_estate')
          return
        }
        const js = (await res.json()) as { domain?: string }
        const d = (js?.domain || '').trim() || 'real_estate'
        if (alive) setTenantDomain(d)
      } catch {
        if (alive) setTenantDomain('real_estate')
      }
    }
    loadDomain()
    return () => { alive = false }
  }, [authed, tenantId])

  useEffect(() => {
    let alive = true
    async function loadActiveTenant() {
      try {
        if (!authed) {
          if (alive) setActiveTenantName(null)
          return
        }
        const res = await apiFetch('/api/ui/tenant', { cache: 'no-store' })
        if (!res.ok) {
          if (alive) setActiveTenantName(null)
          return
        }
        const js = (await res.json()) as { tenant_name?: string | null }
        const name = (js?.tenant_name || '').trim() || null;
        if (alive) setActiveTenantName(name)
      } catch {
        if (alive) setActiveTenantName(null)
      }
    }
    loadActiveTenant()
    return () => { alive = false }
  }, [authed, tenantId])

  useEffect(() => {
    try {
      setShowSuper(!!localStorage.getItem('ui_super_admin_key'))
    } catch {
      setShowSuper(false)
    }
  }, [cfg])

  useEffect(() => {
    try {
      setCatalogOpen(localStorage.getItem('ui_nav_catalog_open') === '1')
      setAdminOpen(localStorage.getItem('ui_nav_admin_open') === '1')
    } catch {
      setCatalogOpen(false)
      setAdminOpen(false)
    }
  }, [])


  function toggleCatalog() {
    setCatalogOpen((prev) => {
      const next = !prev
      try { localStorage.setItem('ui_nav_catalog_open', next ? '1' : '0') } catch (e) { void e }
      return next
    })
  }

  function toggleAdmin() {
    setAdminOpen((prev) => {
      const next = !prev
      try { localStorage.setItem('ui_nav_admin_open', next ? '1' : '0') } catch (e) { void e }
      return next
    })
  }

  function onLogout() {
    clearToken()
    setMe(null)
    setTenantDomain('real_estate')
    navigate('/login')
  }

  const primaryGroupLabel = tenantDomain === 'car_dealer' ? 'Automotivo' : 'Imobiliário'
  const isCarDealer = tenantDomain === 'car_dealer'
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
              <div className="text-xs text-slate-300">{activeTenantName || me?.tenant_name || cfg?.branding?.tenantName || 'Tenant'}</div>
            </div>
          </Link>
        </div>
        <nav className="p-4 space-y-2">
          <div className="px-3 py-2 text-xs uppercase tracking-wide text-slate-400 font-semibold">{primaryGroupLabel}</div>
          {isCarDealer ? (
            <Item to="/catalog/vehicles" label="Veículos" />
          ) : (
            <>
              <Item to="/imoveis" label="Imóveis" />
              <Item to="/import" label="Importar CSV" />
            </>
          )}
          <Item to="/leads" label="Leads" />
          <Item to="/ops" label="Operações" />
          <Item to="/reports" label="Relatórios" />

          {authed && me?.role === 'admin' && (
            <>
              <button
                type="button"
                onClick={toggleCatalog}
                className="w-full flex items-center px-3 py-2 text-xs uppercase tracking-wide font-semibold text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg"
              >
                <span>Catálogo</span>
                <span className="ml-auto text-slate-500">{catalogOpen ? '−' : '+'}</span>
              </button>
              {catalogOpen && (
                <>
                  {!isCarDealer && <SubItem to="/catalog/vehicles" label="Veículos" />}
                  <SubItem to="/catalog/admin" label="Admin do Catálogo" />
                </>
              )}
            </>
          )}

          {authed && me?.role === 'admin' && (
            <>
              <button
                type="button"
                onClick={toggleAdmin}
                className="w-full flex items-center px-3 py-2 text-xs uppercase tracking-wide font-semibold text-slate-400 hover:text-white hover:bg-slate-700/50 rounded-lg"
              >
                <span>Admin</span>
                <span className="ml-auto text-slate-500">{adminOpen ? '−' : '+'}</span>
              </button>
              {adminOpen && (
                <>
                  <Item to="/users" label="Usuários" />
                  <Item to="/flows" label="Flows" />
                  {showSuper && <Item to="/super/tenants" label="Tenants" />}
                </>
              )}
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

function SubItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }: { isActive: boolean }) =>
        `group flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-all duration-200 ml-6 ${
          isActive
            ? 'bg-primary-600 text-white shadow-lg shadow-primary-600/25'
            : 'text-slate-300 hover:text-white hover:bg-slate-700/50'
        }`
      }
    >
      {({ isActive }: { isActive: boolean }) => (
        <>
          <span className="truncate">{label}</span>
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
