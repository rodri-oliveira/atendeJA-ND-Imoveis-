import React, { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiFetch, isAuthenticated } from '../lib/auth'

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
  const navigate = useNavigate()
  const [isAdmin, setIsAdmin] = useState(false)
  const [data, setData] = useState<Detalhes | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Helper: aceita URLs relativas, localhost e IPs (backend já normaliza externas)
  const toDirect = (url?: string | null) => {
    if (!url) return ''
    try {
      const u = String(url)
      if (u.startsWith('/')) return u
      if (u.startsWith('http://') || u.startsWith('https://')) {
        const parsed = new URL(u)
        const host = parsed.hostname || ''
        // aceita localhost/IP ou host com ponto
        const isIPv4 = /^\d{1,3}(?:\.\d{1,3}){3}$/.test(host)
        if (host === 'localhost' || host === '::1' || isIPv4 || host.includes('.')) return u
      }
      return ''
    } catch {
      return ''
    }
  }

  async function fetchDetails() {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api/re/imoveis/${encodeURIComponent(id)}/detalhes`, { cache: 'no-store' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const js = await res.json()
      try {
        console.groupCollapsed('[DETALHES] payload', { id })
        console.debug('payload.raw', js)
        if (Array.isArray(js?.imagens)) {
          console.debug('payload.images.count', js.imagens.length)
          console.debug('payload.images.sample', js.imagens.slice(0, 10).map((i: any) => i?.url))
        }
        console.groupEnd()
      } catch {}
      setData(js)
    } catch (e: any) {
      setError(e?.message || 'erro')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDetails()
    // Descobre papel do usuário via backend (JWT)
    ;(async () => {
      try {
        if (!isAuthenticated()) { setIsAdmin(false); return }
        const res = await apiFetch('/api/auth/me')
        if (!res.ok) { setIsAdmin(false); return }
        const js = await res.json()
        setIsAdmin(js?.role === 'admin')
      } catch {
        setIsAdmin(false)
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  // Ações admin
  async function onSoftDelete() {
    if (!id) return
    if (!confirm('Arquivar este imóvel? Ele ficará inativo.')) return
    const res = await apiFetch(`/api/admin/re/imoveis/${encodeURIComponent(id)}`, { method: 'DELETE' })
    if (res.ok) navigate('/imoveis')
  }

  async function onHardDelete() {
    if (!id) return
    if (!confirm('Excluir PERMANENTEMENTE este imóvel e seus arquivos? Esta ação não pode ser desfeita.')) return
    const res = await apiFetch(`/api/admin/re/imoveis/${encodeURIComponent(id)}/hard`, { method: 'DELETE' })
    if (res.ok) navigate('/imoveis')
  }

  async function onSetCover(imageId: number) {
    if (!id) return
    const res = await apiFetch(`/api/admin/re/imoveis/${encodeURIComponent(id)}/imagens/${imageId}/capa`, { method: 'PATCH' })
    if (res.ok) await fetchDetails()
  }

  async function onDeleteImage(imageId: number) {
    if (!id) return
    if (!confirm('Remover esta imagem?')) return
    const res = await apiFetch(`/api/admin/re/imoveis/${encodeURIComponent(id)}/imagens/${imageId}`, { method: 'DELETE' })
    if (res.ok) await fetchDetails()
  }

  async function moveImage(imageId: number, delta: number) {
    if (!id || !data?.imagens?.length) return
    const arr = [...data.imagens]
    const idx = arr.findIndex(i => i.id === imageId)
    if (idx < 0) return
    const newIdx = Math.max(0, Math.min(arr.length - 1, idx + delta))
    if (newIdx === idx) return
    const removed = arr.splice(idx, 1)
    const item = removed[0]
    if (!item) return
    arr.splice(newIdx, 0, item)
    // Monta payload de reorder e envia
    const items = arr.map((it, i) => ({ id: it.id, ordem: i }))
    const res = await apiFetch(`/api/admin/re/imoveis/${encodeURIComponent(id)}/imagens/reorder`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ items })
    })
    if (res.ok) setData({ ...data, imagens: arr })
  }

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
                <div className="flex items-center gap-2">
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
                    {data.tipo === 'apartment' ? 'Apartamento' : data.tipo === 'house' ? 'Casa' : data.tipo}
                  </span>
                  {isAdmin && (
                    <div className="flex items-center gap-2">
                      <button className="text-xs px-2 py-1 rounded bg-blue-600 text-white hover:bg-blue-700" onClick={() => navigate(`/imoveis/${id}/editar`)}>Editar</button>
                      <button className="text-xs px-2 py-1 rounded bg-amber-600 text-white hover:bg-amber-700" onClick={onSoftDelete}>Arquivar</button>
                      <button className="text-xs px-2 py-1 rounded bg-red-600 text-white hover:bg-red-700" onClick={onHardDelete}>Excluir</button>
                    </div>
                  )}
                </div>
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
                    if (!u) return false
                    if (u.startsWith('/')) return true
                    if (u.startsWith('http://') || u.startsWith('https://')) {
                      const parsed = new URL(u)
                      const host = parsed.hostname || ''
                      const isIPv4 = /^\d{1,3}(?:\.\d{1,3}){3}$/.test(host)
                      return host === 'localhost' || host === '::1' || isIPv4 || host.includes('.')
                    }
                    return false
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
                        <div key={img.id} className="relative aspect-[4/3] overflow-hidden rounded-lg border border-slate-200 bg-slate-100">
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
                          {isAdmin && (
                            <div className="absolute left-1 top-1 flex gap-1">
                              <button className="text-[10px] px-2 py-0.5 rounded bg-slate-900/80 text-white hover:bg-slate-900" onClick={() => onSetCover(img.id)}>Capa</button>
                              <button className="text-[10px] px-2 py-0.5 rounded bg-red-600/90 text-white hover:bg-red-700" onClick={() => onDeleteImage(img.id)}>Remover</button>
                            </div>
                          )}
                          {isAdmin && (
                            <div className="absolute right-1 bottom-1 flex gap-1">
                              <button className="text-[10px] px-2 py-0.5 rounded bg-slate-800/80 text-white hover:bg-slate-800" onClick={() => moveImage(img.id, -1)}>↑</button>
                              <button className="text-[10px] px-2 py-0.5 rounded bg-slate-800/80 text-white hover:bg-slate-800" onClick={() => moveImage(img.id, 1)}>↓</button>
                            </div>
                          )}
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
