import React, { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { apiFetch, isAuthenticated } from '../lib/auth'

export default function RequireAdmin({ children }: { children: React.ReactNode }) {
  const authed = isAuthenticated()
  const location = useLocation()
  const [loading, setLoading] = useState(true)
  const [isAdmin, setIsAdmin] = useState(false)
  const [isSuper, setIsSuper] = useState(false)

  useEffect(() => {
    let alive = true

    async function load() {
      try {
        let superKey: string | null = null
        try {
          superKey = localStorage.getItem('ui_super_admin_key')
        } catch {
          superKey = null
        }
        if (superKey) {
          if (alive) {
            setIsSuper(true)
            setIsAdmin(true)
            setLoading(false)
          }
          return
        }

        if (!authed) {
          if (alive) {
            setIsSuper(false)
            setIsAdmin(false)
            setLoading(false)
          }
          return
        }

        const res = await apiFetch('/api/auth/me')
        if (!res.ok) {
          if (alive) {
            setIsAdmin(false)
            setLoading(false)
          }
          return
        }

        const js = (await res.json()) as { role?: string }
        if (alive) {
          setIsSuper(false)
          setIsAdmin(js.role === 'admin')
          setLoading(false)
        }
      } catch {
        if (alive) {
          setIsSuper(false)
          setIsAdmin(false)
          setLoading(false)
        }
      }
    }

    void load()
    return () => {
      alive = false
    }
  }, [authed])

  if (!authed && !isSuper) {
    return <Navigate to="/login" replace state={{ redirectTo: location.pathname + location.search }} />
  }

  if (loading) {
    return <div className="p-6 text-sm text-slate-600">Carregando...</div>
  }

  if (!isAdmin) {
    return <Navigate to="/imoveis" replace />
  }

  return <>{children}</>
}
