import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

interface Imagem {
  id: number
  url: string
  is_capa: boolean
  ordem: number
}

interface Detalhes {
  id: number
  titulo: string
  descricao?: string | null
  tipo: 'apartment' | 'house' | string
  finalidade: 'sale' | 'rent' | string
  preco: number
  cidade: string
  estado: string
  bairro?: string | null
  dormitorios?: number | null
  banheiros?: number | null
  suites?: number | null
  vagas?: number | null
  area_total?: number | null
  area_util?: number | null
  imagens: Imagem[]
}

export default function ImovelDetalhes() {
  const { id } = useParams()
  const [data, setData] = useState<Detalhes | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Helper: usa URL direta (backend já normaliza e devolve apenas http/https válidos)
  const toDirect = (url?: string | null) => {
    if (!url) return ''
    try {
      const u = String(url)
      if (u.startsWith('/')) return u
      if (u.startsWith('http://') || u.startsWith('https://')) {
        const parsed = new URL(u)
        if (!parsed.hostname || !parsed.hostname.includes('.')) return ''
        return u
      }
      return ''
    } catch {
      return ''
    }
  }

  useEffect(() => {
    let alive = true
    async function load() {
      if (!id) return
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(`/api/re/imoveis/${encodeURIComponent(id)}/detalhes`, { cache: 'no-store' })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const js = await res.json()
        // DEBUG: log bruto da resposta
        try {
          console.groupCollapsed('[DETALHES] payload', { id })
          console.debug('payload.raw', js)
          if (Array.isArray(js?.imagens)) {
            console.debug('payload.images.count', js.imagens.length)
            console.debug('payload.images.sample', js.imagens.slice(0, 10).map((i: any) => i?.url))
          }
          console.groupEnd()
        } catch {}
        if (alive) setData(js)
      } catch (e: any) {
        if (alive) setError(e?.message || 'erro')
      } finally {
        if (alive) setLoading(false)
      }
    }
    load()
    return () => { alive = false }
  }, [id])

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <Link to="/imoveis" className="inline-flex items-center gap-1 text-primary-600 hover:underline focus:outline-none focus:ring-2 focus:ring-primary-300 rounded px-1">
            <span aria-hidden>←</span>
            <span>Voltar</span>
          </Link>
          <span className="text-slate-400">/</span>
          <span className="text-slate-800 font-medium">Detalhes do Imóvel</span>
        </div>
      </header>
      {loading && <div className="text-sm text-gray-600">Carregando...</div>}
      {error && <div className="text-sm text-red-600">Erro: {error}</div>}
      {!loading && !error && data && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold text-slate-900">{data.titulo}</h2>
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
                  {data.tipo === 'apartment' ? 'Apartamento' : data.tipo === 'house' ? 'Casa' : data.tipo}
                </span>
              </div>
              <div className="text-sm text-slate-600">
                {data.finalidade === 'sale' ? 'Venda' : 'Locação'} · {data.cidade}-{data.estado}
              </div>
              <div className="text-lg font-semibold text-primary-600">
                {data.preco > 0
                  ? new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(data.preco)
                  : 'Consulte'}
              </div>
              {data.descricao && <p className="text-sm text-slate-700">{data.descricao}</p>}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 text-xs text-slate-700">
                {typeof data.dormitorios === 'number' && <div><span className="text-slate-500">Dormitórios:</span> {data.dormitorios}</div>}
                {typeof data.banheiros === 'number' && <div><span className="text-slate-500">Banheiros:</span> {data.banheiros}</div>}
                {typeof data.suites === 'number' && <div><span className="text-slate-500">Suítes:</span> {data.suites}</div>}
                {typeof data.vagas === 'number' && <div><span className="text-slate-500">Vagas:</span> {data.vagas}</div>}
                {typeof data.area_total === 'number' && <div><span className="text-slate-500">Área total:</span> {data.area_total} m²</div>}
                {typeof data.area_util === 'number' && <div><span className="text-slate-500">Área útil:</span> {data.area_util} m²</div>}
              </div>
            </div>
          </div>
          {!!data.imagens?.length && (
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-medium text-slate-900 mb-2">Galeria de imagens</h3>
              {(() => {
                // Filtra HTTPS e hosts válidos para depuração e uso na renderização
                const filteredImages = (data.imagens || []).filter((img) => {
                  try {
                    const u = String(img?.url || '')
                    if (!u || !(u.startsWith('http://') || u.startsWith('https://'))) return false
                    const parsed = new URL(u)
                    return !!parsed.hostname && parsed.hostname.includes('.')
                  } catch { return false }
                })
                try {
                  console.groupCollapsed('[DETALHES] imagens (filtradas)', { id })
                  console.debug('filtered.count', filteredImages.length)
                  console.debug('filtered.sample', filteredImages.slice(0, 10).map((i: any) => i?.url))
                  console.debug('all.count', data.imagens.length)
                  console.groupEnd()
                } catch {}
                return (
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                    {filteredImages.map((img) => {
                      const src = toDirect(img.url)
                      // Usar proxy para imagens externas (CDN)
                      const proxiedSrc = src && src.includes('cdn-imobibrasil.com.br') 
                        ? `/api/re/images/proxy?url=${encodeURIComponent(src)}`
                        : src
                      return (
                        <div key={img.id} className="aspect-[4/3] overflow-hidden rounded-lg border border-slate-200 bg-slate-100">
                          {proxiedSrc ? (
                            <img
                              src={proxiedSrc}
                              alt={`Imagem ${img.id}`}
                              className="w-full h-full object-cover transition-transform duration-200 hover:scale-[1.02]"
                              onError={(e) => {
                                try {
                                  console.error('[IMG_ERROR] detalhes', { id, imgId: img.id, url: proxiedSrc, original: src })
                                } catch {}
                                const el = e.currentTarget as HTMLImageElement
                                el.style.display = 'none'
                              }}
                              onLoad={() => { try { console.debug('[IMG_OK] detalhes', { id, imgId: img.id, url: proxiedSrc }) } catch {} }}
                            />
                          ) : null}
                        </div>
                      )
                    })}
                  </div>
                )
              })()}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
