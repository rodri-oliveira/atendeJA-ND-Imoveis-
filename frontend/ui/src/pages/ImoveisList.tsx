import React, { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../lib/auth'

interface Imovel {
  id: number
  titulo: string
  tipo: 'apartment' | 'house' | string
  finalidade: 'sale' | 'rent' | string
  preco: number
  cidade: string
  estado: string
  bairro?: string | null
  dormitorios?: number | null
  ativo: boolean
  cover_image_url?: string | null
}

export default function ImoveisList() {
  const navigate = useNavigate()
  // Helper: usa URL direta (backend já normaliza e devolve apenas http/https válidos)
  const toDirect = (url?: string | null) => {
    if (!url) return ''
    try {
      const u = String(url)
      if (u.startsWith('http://') || u.startsWith('https://') || u.startsWith('/')) return u
      return ''
    } catch {
      return ''
    }
  }
  const [data, setData] = useState<Imovel[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [total, setTotal] = useState<number>(0)
  const [typeCounts, setTypeCounts] = useState<Record<string, number>>({})
  // filtros
  const [finalidade, setFinalidade] = useState<string>('')
  const [tipo, setTipo] = useState<string>('')
  const [cidade, setCidade] = useState<string>('')
  const [estado, setEstado] = useState<string>('')
  const [precoMin, setPrecoMin] = useState<string>('')
  const [precoMax, setPrecoMax] = useState<string>('')
  const [dormMin, setDormMin] = useState<string>('')
  // paginação
  const [limit] = useState<number>(12)
  const [offset, setOffset] = useState<number>(0)

  // Debounce helper
  function useDebouncedValue<T>(value: T, delay = 300) {
    const [debounced, setDebounced] = useState<T>(value)
    useEffect(() => {
      const t = setTimeout(() => setDebounced(value), delay)
      return () => clearTimeout(t)
    }, [value, delay])
    return debounced
  }

  // Valores debounced para reduzir requisições durante digitação
  const cidadeQ = useDebouncedValue(cidade)
  const estadoQ = useDebouncedValue(estado)
  const precoMinQ = useDebouncedValue(precoMin)
  const precoMaxQ = useDebouncedValue(precoMax)
  const dormMinQ = useDebouncedValue(dormMin)

  function clearFilters() {
    setFinalidade('')
    setTipo('')
    setCidade('')
    setEstado('')
    setPrecoMin('')
    setPrecoMax('')
    setDormMin('')
    setOffset(0)
  }

  // Ler filtros do querystring ao montar
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const f = params.get('finalidade') || ''
    const t = params.get('tipo') || ''
    const c = params.get('cidade') || ''
    const e = params.get('estado') || ''
    const pmin = params.get('preco_min') || ''
    const pmax = params.get('preco_max') || ''
    const dmin = params.get('dormitorios_min') || ''
    const off = params.get('offset') || '0'
    if (f) setFinalidade(f)
    if (t) setTipo(t)
    if (c) setCidade(c)
    if (e) setEstado(e)
    if (pmin) setPrecoMin(pmin)
    if (pmax) setPrecoMax(pmax)
    if (dmin) setDormMin(dmin)
    if (off) setOffset(Number(off) || 0)
  }, [])

  useEffect(() => {
    let alive = true
    async function loadTypeCounts() {
      try {
        const res = await apiFetch('/api/re/imoveis/type-counts', { cache: 'no-store' })
        if (!res.ok) return
        const js = await res.json()
        const m: Record<string, number> = {}
        for (const row of (js?.type_counts || [])) {
          if (row && row.tipo) m[String(row.tipo)] = Number(row.count) || 0
        }
        if (alive) setTypeCounts(m)
      } catch {
        if (alive) setTypeCounts({})
      }
    }
    loadTypeCounts()
    return () => { alive = false }
  }, [])

  const tipoOptions = useMemo(() => {
    const base = [
      { value: 'apartment', label: 'Apartamento' },
      { value: 'house', label: 'Casa' },
      { value: 'commercial', label: 'Comercial' },
      { value: 'land', label: 'Terreno' },
    ]
    return base.map(o => ({ ...o, count: typeCounts[o.value] ?? 0 }))
  }, [typeCounts])

  // Atualizar querystring quando filtros/offset mudarem (usando valores debounced)
  useEffect(() => {
    const params = new URLSearchParams()
    if (finalidade) params.set('finalidade', finalidade)
    if (tipo) params.set('tipo', tipo)
    if (cidadeQ) params.set('cidade', cidadeQ)
    if (estadoQ) params.set('estado', estadoQ)
    if (precoMinQ) params.set('preco_min', precoMinQ)
    if (precoMaxQ) params.set('preco_max', precoMaxQ)
    if (dormMinQ) params.set('dormitorios_min', dormMinQ)
    if (offset) params.set('offset', String(offset))
    const qs = params.toString()
    const newUrl = `${window.location.pathname}${qs ? `?${qs}` : ''}`
    if (newUrl !== window.location.pathname + window.location.search) {
      window.history.replaceState({}, '', newUrl)
    }
  }, [finalidade, tipo, cidadeQ, estadoQ, precoMinQ, precoMaxQ, dormMinQ, offset])

  // Resetar offset ao mudar qualquer filtro
  useEffect(() => {
    setOffset(0)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finalidade, tipo, cidade, estado, precoMin, precoMax, dormMin])

  const queryString = useMemo(() => {
    const params = new URLSearchParams()
    if (finalidade) params.set('finalidade', finalidade)
    if (tipo) params.set('tipo', tipo)
    if (cidadeQ) params.set('cidade', cidadeQ)
    if (estadoQ) params.set('estado', estadoQ)
    if (precoMinQ) params.set('preco_min', precoMinQ)
    if (precoMaxQ) params.set('preco_max', precoMaxQ)
    if (dormMinQ) params.set('dormitorios_min', dormMinQ)
    params.set('limit', String(limit))
    params.set('offset', String(offset))
    return params.toString()
  }, [finalidade, tipo, cidadeQ, estadoQ, precoMinQ, precoMaxQ, dormMinQ, limit, offset])

  useEffect(() => {
    let alive = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const url = `/api/re/imoveis${queryString ? `?${queryString}` : ''}`
        const res = await apiFetch(url, { cache: 'no-store' })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const js = await res.json()
        const hdr = res.headers.get('X-Total-Count')
        const totalCount = hdr ? Number(hdr) : (Array.isArray(js) ? js.length : 0)
        if (alive) {
          setData(js)
          setTotal(Number.isFinite(totalCount) ? totalCount : 0)
        }
      } catch (e: any) {
        if (alive) setError(e?.message || 'erro')
      } finally {
        if (alive) setLoading(false)
      }
    }
    load()
    return () => { alive = false }
  }, [queryString])

  return (
    <section className="space-y-4">
      <header className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold text-slate-800">Imóveis</h1>
            {!loading && !error && (
              <span className="inline-flex items-center px-3 py-1 text-sm font-medium rounded-full bg-primary-100 text-primary-800">
                {total === 1 ? '1 resultado' : `${total} resultados`}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <div className="text-sm text-slate-500">Lista dos imóveis ativos</div>
            <button
              type="button"
              onClick={() => navigate('/imoveis/novo')}
              className="px-3 py-2 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-all"
            >
              Cadastrar imóvel
            </button>
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <form className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 items-end" onSubmit={(e) => e.preventDefault()}>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Finalidade</label>
              <select value={finalidade} onChange={e => setFinalidade(e.target.value)} className="w-full rounded-lg border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors">
                <option value="">Todas</option>
                <option value="sale">Venda</option>
                <option value="rent">Locação</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Tipo</label>
              <select value={tipo} onChange={e => setTipo(e.target.value)} className="w-full rounded-lg border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors">
                <option value="">Todos</option>
                {tipoOptions.map(o => (
                  <option key={o.value} value={o.value} disabled={o.count === 0}>
                    {o.label} ({o.count})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Cidade</label>
              <input value={cidade} onChange={e => setCidade(e.target.value)} className="w-full rounded-lg border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors" placeholder="Ex.: São Paulo" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Estado (UF)</label>
              <input value={estado} onChange={e => setEstado(e.target.value.toUpperCase())} className="w-full rounded-lg border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors" placeholder="SP" maxLength={2} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Preço mín.</label>
              <input type="number" value={precoMin} onChange={e => setPrecoMin(e.target.value)} className="w-full rounded-lg border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors" placeholder="0" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Preço máx.</label>
              <input type="number" value={precoMax} onChange={e => setPrecoMax(e.target.value)} className="w-full rounded-lg border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors" placeholder="" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Dormitórios mín.</label>
              <input type="number" value={dormMin} onChange={e => setDormMin(e.target.value)} className="w-full rounded-lg border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-colors" placeholder="" />
            </div>
            <div className="lg:col-span-4" />
            <div className="flex justify-end">
              <button type="button" onClick={clearFilters} className="px-4 py-2 text-sm font-medium rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 hover:border-slate-400 transition-all duration-200">
                Limpar filtros
              </button>
            </div>
          </form>
        </div>
      </header>
      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="rounded-xl border border-slate-200 bg-white shadow-card overflow-hidden">
              {/* Skeleton para imagem */}
              <div className="h-48 skeleton"></div>
              
              <div className="p-5 space-y-4">
                {/* Skeleton para título */}
                <div className="space-y-2">
                  <div className="h-5 skeleton rounded w-3/4"></div>
                  <div className="h-4 skeleton rounded w-1/2"></div>
                </div>
                
                {/* Skeleton para preço */}
                <div className="flex items-center justify-between">
                  <div className="h-7 skeleton rounded w-24"></div>
                  <div className="h-4 skeleton rounded w-16"></div>
                </div>
                
                {/* Skeleton para botão */}
                <div className="h-10 skeleton rounded"></div>
              </div>
            </div>
          ))}
        </div>
      )}
      {error && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-4">Erro: {error}</div>}
      {!loading && !error && (data?.length ?? 0) === 0 && (
        <div className="text-center py-12">
          <div className="text-slate-400 text-lg mb-2">Nenhum imóvel encontrado</div>
          <div className="text-sm text-slate-500">Ajuste os filtros acima e tente novamente.</div>
        </div>
      )}
      {!loading && !error && (
        <div className="flex items-center justify-end text-xs text-gray-600">
          <div>
            Página {Math.floor(offset / limit) + 1} de {Math.max(1, Math.ceil((total || 0) / limit))} • {total} resultados
          </div>
        </div>
      )}
      {!loading && !error && (data?.length ?? 0) > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {(data ?? []).map((p, index) => (
            <article 
              key={p.id} 
              className="group rounded-xl border border-slate-200 bg-white shadow-card hover:shadow-hover transition-all duration-300 overflow-hidden hover-lift card-entrance"
              style={{ animationDelay: `${index * 0.1}s` }}
            >
              {/* Imagem de capa (quando disponível) com fallback visual */}
              <div className="h-48 relative overflow-hidden bg-gradient-to-br from-slate-100 to-slate-200">
                {p.cover_image_url ? (() => {
                  const direct = toDirect(p.cover_image_url)
                  const src = direct && direct.includes('cdn-imobibrasil.com.br')
                    ? `/api/re/images/proxy?url=${encodeURIComponent(direct)}`
                    : direct
                  return src ? (
                    <img
                      src={src}
                      alt={p.titulo}
                      className="absolute inset-0 w-full h-full object-cover"
                      onError={(e) => {
                        try { console.error('[IMG_ERROR] list', { id: p.id, url: src, original: direct }) } catch {}
                        const el = e.currentTarget as HTMLImageElement
                        el.style.display = 'none'
                      }}
                      onLoad={() => { try { console.debug('[IMG_OK] list', { id: p.id, url: src }) } catch {} }}
                    />
                  ) : null
                })() : null}
                <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent"></div>
                <div className="absolute top-3 left-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    p.finalidade === 'sale'
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-amber-100 text-amber-800'
                  }`}>
                    {p.finalidade === 'sale' ? 'Venda' : 'Locação'}
                  </span>
                </div>
                <div className="absolute top-3 right-3">
                  <span className="px-2 py-1 rounded-full text-xs font-medium bg-white/90 text-slate-700">
                    {p.tipo === 'apartment' ? 'Apartamento' : p.tipo === 'house' ? 'Casa' : p.tipo}
                  </span>
                </div>
              </div>
              
              <div className="p-5 space-y-4">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900 group-hover:text-primary-600 transition-colors duration-200 line-clamp-2">
                    {p.titulo}
                  </h2>
                  <div className="text-sm text-slate-500 mt-1">
                    {p.cidade}-{p.estado}
                  </div>
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="text-2xl font-bold text-primary-600">
                    {p.preco > 0
                      ? new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(p.preco)
                      : 'Consulte'}
                  </div>
                  {typeof p.dormitorios === 'number' && (
                    <div className="text-sm text-slate-500">
                      {p.dormitorios} dorm.
                    </div>
                  )}
                </div>
                
                <div className="pt-2">
                  <Link 
                    to={`/imoveis/${p.id}`} 
                    className="block w-full text-center px-4 py-2.5 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-all duration-200 hover-lift"
                  >
                    Ver Detalhes
                  </Link>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
      {!loading && !error && (
        <div className="flex items-center justify-between pt-6">
          <button
            className="flex items-center px-4 py-2 text-sm font-medium rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
            onClick={() => setOffset(Math.max(0, offset - limit))}
            disabled={offset === 0}
          >
            ← Anterior
          </button>
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-600">Página</span>
            <span className="px-3 py-1 bg-primary-100 text-primary-800 rounded-lg font-medium">
              {Math.floor(offset / limit) + 1}
            </span>
            <span className="text-sm text-slate-500">de {Math.max(1, Math.ceil((total || 0) / limit))}</span>
          </div>
          <button
            className="flex items-center px-4 py-2 text-sm font-medium rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
            onClick={() => setOffset(offset + limit)}
            disabled={offset + limit >= (total || 0)}
          >
            Próxima →
          </button>
        </div>
      )}
    </section>
  )
}
