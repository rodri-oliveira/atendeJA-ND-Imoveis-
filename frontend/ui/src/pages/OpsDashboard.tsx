import React, { useEffect, useState } from 'react'

interface OpsConfig {
  app_env: string
  wa_provider: string
  default_tenant: string
  re_read_only: boolean
  version: string
}

export default function OpsDashboard() {
  const [config, setConfig] = useState<OpsConfig | null>(null)
  const [ping, setPing] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [cRes, pRes] = await Promise.all([
          fetch('/api/ops/config', { cache: 'no-store' }),
          fetch('/api/ops/ping/meta', { cache: 'no-store' }),
        ])
        if (!cRes.ok) throw new Error(`config HTTP ${cRes.status}`)
        if (!pRes.ok) throw new Error(`ping HTTP ${pRes.status}`)
        const c = await cRes.json()
        const p = await pRes.json()
        if (alive) {
          setConfig(c)
          setPing(p)
        }
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : 'erro'
        if (alive) setError(msg)
      } finally {
        if (alive) setLoading(false)
      }
    }
    load()
    return () => { alive = false }
  }, [])

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Operações</h1>
        <div className="text-xs text-gray-500">Config e Ping</div>
      </header>
      {loading && <div className="text-sm text-gray-600">Carregando...</div>}
      {error && <div className="text-sm text-red-600">Erro: {error}</div>}
      {!loading && !error && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-medium text-gray-900 mb-2">Config</h2>
            <dl className="text-sm text-gray-700 space-y-1">
              <div className="flex justify-between"><dt>Ambiente</dt><dd className="font-mono">{config?.app_env}</dd></div>
              <div className="flex justify-between"><dt>Provider</dt><dd className="font-mono">{config?.wa_provider}</dd></div>
              <div className="flex justify-between"><dt>Tenant</dt><dd className="font-mono">{config?.default_tenant}</dd></div>
              <div className="flex justify-between"><dt>Read-only</dt><dd className="font-mono">{String(config?.re_read_only)}</dd></div>
              <div className="flex justify-between"><dt>Versão</dt><dd className="font-mono">{config?.version}</dd></div>
            </dl>
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-medium text-gray-900 mb-2">Ping Meta</h2>
            <dl className="text-sm text-gray-700 space-y-1">
              <div className="flex justify-between"><dt>Env OK</dt><dd className="font-mono">{String(ping?.env_ok)}</dd></div>
              <div className="flex justify-between"><dt>Alcance</dt><dd className="font-mono">{String(ping?.graph_reachable)}</dd></div>
              {'graph_head_status' in (ping || {}) && (
                <div className="flex justify-between"><dt>Status</dt><dd className="font-mono">{String((ping as Record<string, unknown> | null)?.graph_head_status ?? '')}</dd></div>
              )}
            </dl>
          </div>
        </div>
      )}
    </section>
  )
}
