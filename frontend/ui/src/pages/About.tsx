import React, { useEffect, useState } from 'react'

interface OpsConfig {
  app_env: string
  wa_provider: string
  default_tenant: string
  re_read_only: boolean
  version: string
}

export default function About() {
  const [cfg, setCfg] = useState<OpsConfig | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const r = await fetch('/api/ops/config', { cache: 'no-store' })
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        const js = await r.json()
        if (alive) setCfg(js)
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : 'erro'
        if (alive) setErr(msg)
      }
    })()
    return () => { alive = false }
  }, [])

  const frontendVersion = '0.1.0'

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">Sobre / Docs</h1>
        <div className="text-sm text-slate-500">AtendeJá — ND Imóveis</div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-card">
          <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
            🔗 Links úteis
          </h2>
          <ul className="space-y-3">
            <li>
              <a 
                className="flex items-center gap-2 text-primary-600 hover:text-primary-700 transition-colors font-medium" 
                href="/api/ops/config" 
                target="_blank" 
                rel="noreferrer"
              >
                🛠️ GET /ops/config
              </a>
            </li>
            <li>
              <a 
                className="flex items-center gap-2 text-primary-600 hover:text-primary-700 transition-colors font-medium" 
                href="/api/ops/ping/meta" 
                target="_blank" 
                rel="noreferrer"
              >
                📞 GET /ops/ping/meta
              </a>
            </li>
          </ul>
        </div>
        
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-card">
          <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
            📊 Versões
          </h2>
          <dl className="space-y-3">
            <div className="flex justify-between items-center p-3 bg-slate-50 rounded-lg">
              <dt className="font-medium text-slate-700">Frontend</dt>
              <dd className="font-mono text-sm bg-white px-2 py-1 rounded border">{frontendVersion}</dd>
            </div>
            <div className="flex justify-between items-center p-3 bg-slate-50 rounded-lg">
              <dt className="font-medium text-slate-700">Backend</dt>
              <dd className="font-mono text-sm bg-white px-2 py-1 rounded border">
                {cfg?.version ? cfg.version : <div className="h-4 skeleton rounded w-16"></div>}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-card">
        <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
          💡 Dicas rápidas
        </h2>
        <ul className="space-y-4">
          <li className="flex items-start gap-3 p-3 bg-slate-50 rounded-lg">
            <span className="text-emerald-600 mt-0.5">✓</span>
            <div>
              <span className="font-medium text-slate-900">Importar CSV de Imóveis</span>
              <p className="text-sm text-slate-600 mt-1">
                Acesse <span className="font-mono bg-white px-1 rounded">Imobiliário &gt; Importar CSV</span>. Após enviar, clique em &quot;Ver imóveis&quot;.
              </p>
            </div>
          </li>
          <li className="flex items-start gap-3 p-3 bg-slate-50 rounded-lg">
            <span className="text-primary-600 mt-0.5">🔗</span>
            <div>
              <span className="font-medium text-slate-900">Filtros Persistentes</span>
              <p className="text-sm text-slate-600 mt-1">
                Filtros de <span className="font-mono bg-white px-1 rounded">Imóveis</span> ficam persistidos na URL. Compartilhe a URL para manter contexto.
              </p>
            </div>
          </li>
          <li className="flex items-start gap-3 p-3 bg-slate-50 rounded-lg">
            <span className="text-amber-600 mt-0.5">📄</span>
            <div>
              <span className="font-medium text-slate-900">Paginação de Leads</span>
              <p className="text-sm text-slate-600 mt-1">
                Leads possuem paginação com offset persistido no querystring.
              </p>
            </div>
          </li>
        </ul>
        {err && <div className="mt-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">Erro ao consultar /ops/config: {err}</div>}
      </div>
    </section>
  )
}
