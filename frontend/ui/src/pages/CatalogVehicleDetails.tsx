import React, { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiFetch, isAuthenticated } from '../lib/auth'

interface VehicleAttributes {
  price?: number
  year?: number
  km?: number
  make?: string
  model?: string
  transmission?: string
  fuel?: string
  accessories?: string[]
}

interface CatalogMedia {
  id: number
  kind: string
  url: string
  sort_order: number
}

interface CatalogItem {
  id: number
  title: string
  description?: string | null
  attributes: VehicleAttributes
  is_active: boolean
  media?: CatalogMedia[]
}

export default function CatalogVehicleDetails() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState<CatalogItem | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [mainImage, setMainImage] = useState<CatalogMedia | null>(null)
  const [badMediaIds, setBadMediaIds] = useState<Set<number>>(() => new Set())
  const [isAdmin, setIsAdmin] = useState(false)

  const isBadImageUrl = (url: string): boolean => {
    const u = String(url || '').trim().toLowerCase()
    if (!u) return true
    if (u.startsWith('data:')) return true
    if (u.endsWith('.svg') || u.endsWith('.ico')) return true
    const bad = [
      'logo',
      'favicon',
      'sprite',
      'icon',
      'brand',
      'banner',
      'header',
      'footer',
      'navbar',
      'menu',
      'social',
      'whatsapp',
      'facebook',
      'instagram',
      'tiktok',
      'placeholder',
      'noimage',
      'default',
    ]
    return bad.some((k) => u.includes(k))
  }

  const toDirect = (url?: string | null) => {
    if (!url) return ''
    try {
      const u = String(url)
      if (u.startsWith('/')) return u
      if (u.startsWith('http://') || u.startsWith('https://')) {
        const parsed = new URL(u)
        const host = parsed.hostname || ''
        const isIPv4 = /^\d{1,3}(?:\.\d{1,3}){3}$/.test(host)
        if (host === 'localhost' || host === '::1' || isIPv4 || host.includes('.')) return u
      }
      return ''
    } catch {
      return ''
    }
  }

  const images = useMemo(() => {
    const list = (data?.media || []).filter(
      (m) => m.kind === 'image' && !!m.url && !isBadImageUrl(m.url) && !badMediaIds.has(Number(m.id))
    )
    return [...list].sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
  }, [data, badMediaIds])

  const isBannerLike = (w: number, h: number): boolean => {
    if (!w || !h) return false
    const ratio = w / h
    // Logo/banner geralmente é bem "achatado" (muito largo)
    if (ratio >= 2.2) return true
    return false
  }

  const formatPrice = (value: number | null | undefined) => {
    if (value === null || value === undefined) return '—'
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value)
  }

  const characteristics = useMemo(() => {
    if (!data) return []
    const a = data.attributes || {}
    return [
      { icon: '💰', label: 'Preço', value: a.price != null ? formatPrice(a.price) : null },
      { icon: '📅', label: 'Ano', value: a.year != null ? String(a.year) : null },
      { icon: '🛣️', label: 'KM', value: a.km != null ? new Intl.NumberFormat('pt-BR').format(a.km) : null },
      { icon: '🏷️', label: 'Marca', value: a.make || null },
      { icon: '🧩', label: 'Modelo', value: a.model || null },
      { icon: '⚙️', label: 'Câmbio', value: a.transmission || null },
      { icon: '⛽', label: 'Combustível', value: a.fuel || null },
    ].filter((c) => c.value)
  }, [data])

  async function fetchDetails() {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch(`/api/admin/catalog/items/${encodeURIComponent(id)}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const js = (await res.json()) as CatalogItem
      setData(js)
      const first = (js.media || [])
        .filter((m) => m.kind === 'image' && !!m.url && !isBadImageUrl(m.url))
        .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))[0]
      setMainImage(first || null)
    } catch (e: unknown) {
      const err = e as Error
      setError(err?.message || 'erro')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void fetchDetails()
    ;(async () => {
      try {
        if (!isAuthenticated()) {
          setIsAdmin(false)
          return
        }
        const res = await apiFetch('/api/auth/me')
        if (!res.ok) {
          setIsAdmin(false)
          return
        }
        const js = await res.json()
        setIsAdmin(js?.role === 'admin')
      } catch {
        setIsAdmin(false)
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  async function onSoftDelete() {
    if (!id) return
    if (!confirm('Arquivar este veículo? Ele ficará inativo.')) return
    const res = await apiFetch(`/api/admin/catalog/items/${encodeURIComponent(id)}`, { method: 'DELETE' })
    if (res.ok) navigate('/catalog/vehicles')
  }

  async function onHardDelete() {
    if (!id) return
    if (!confirm('Excluir PERMANENTEMENTE este veículo e suas mídias? Esta ação não pode ser desfeita.')) return
    const res = await apiFetch(`/api/admin/catalog/items/${encodeURIComponent(id)}/hard`, { method: 'DELETE' })
    if (res.ok) navigate('/catalog/vehicles')
  }

  return (
    <section className="space-y-6">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <Link
            to="/catalog/vehicles"
            className="inline-flex items-center gap-1 text-primary-600 hover:underline focus:outline-none focus:ring-2 focus:ring-primary-300 rounded px-1"
          >
            <span aria-hidden>←</span>
            <span>Voltar para a lista</span>
          </Link>
        </div>
      </header>

      {loading && <div className="text-center py-12 text-slate-500">Carregando detalhes do veículo...</div>}
      {error && <div className="card text-red-600">Erro ao carregar veículo: {error}</div>}

      {!loading && !error && data && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <div className="space-y-3">
              <div className="aspect-[16/10] bg-slate-100 rounded-xl overflow-hidden border">
                {mainImage ? (
                  <img
                    src={toDirect(mainImage.url)}
                    alt={data.title}
                    className="w-full h-full object-cover"
                    onLoad={(e) => {
                      const el = e.currentTarget as HTMLImageElement
                      const w = el.naturalWidth || 0
                      const h = el.naturalHeight || 0
                      if (isBannerLike(w, h)) {
                        setBadMediaIds((prev) => {
                          const next = new Set(prev)
                          next.add(Number(mainImage.id))
                          return next
                        })
                        const nextImg = images.find((x) => Number(x.id) !== Number(mainImage.id))
                        if (nextImg) setMainImage(nextImg)
                      }
                    }}
                    onError={() => {
                      setBadMediaIds((prev) => {
                        const next = new Set(prev)
                        next.add(Number(mainImage.id))
                        return next
                      })
                      const nextImg = images.find((x) => Number(x.id) !== Number(mainImage.id))
                      if (nextImg) setMainImage(nextImg)
                    }}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-slate-400">Sem foto</div>
                )}
              </div>

              {images.length > 1 && (
                <div className="grid grid-cols-5 md:grid-cols-8 gap-2">
                  {images.map((img) => (
                    <button
                      key={img.id}
                      onClick={() => setMainImage(img)}
                      className={`aspect-square bg-slate-100 rounded-lg overflow-hidden border-2 transition-all ${
                        mainImage?.id === img.id ? 'border-primary-500' : 'border-transparent hover:border-slate-300'
                      }`}
                    >
                      <img src={toDirect(img.url)} alt={data.title} className="w-full h-full object-cover" />
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div>
              <h1 className="text-3xl font-bold text-slate-900">{data.title}</h1>
              <div className="mt-2 flex items-center gap-2">
                <span
                  className={`px-2 py-1 text-xs font-medium rounded-full ${
                    data.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                  }`}
                >
                  {data.is_active ? 'Ativo' : 'Inativo'}
                </span>
                {data.attributes?.year != null && (
                  <span className="px-2 py-1 text-xs font-medium rounded-full bg-slate-100 text-slate-700">{data.attributes.year}</span>
                )}
              </div>
            </div>

            {characteristics.length > 0 && (
              <div className="card">
                <h2 className="card-header">Detalhes</h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mt-4">
                  {characteristics.map((c) => (
                    <div key={c.label} className="flex items-center gap-3">
                      <span className="text-2xl">{c.icon}</span>
                      <div>
                        <div className="text-sm text-slate-600">{c.label}</div>
                        <div className="font-semibold text-slate-800">{String(c.value)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {data.description && (
              <div className="card">
                <h2 className="card-header">Descrição</h2>
                <p className="text-slate-700 mt-4 whitespace-pre-wrap">{data.description}</p>
              </div>
            )}

            {Array.isArray(data.attributes?.accessories) && data.attributes.accessories.length > 0 && (
              <div className="card">
                <h2 className="card-header">Acessórios</h2>
                <div className="mt-4 flex flex-wrap gap-2">
                  {(data.attributes.accessories || []).slice(0, 40).map((a, idx) => (
                    <span key={`${idx}-${a}`} className="px-3 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
                      {a}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="lg:col-span-1">
            <div className="sticky top-4 space-y-4">
              {isAdmin && (
                <div className="card">
                  <h2 className="card-header">Ações do Administrador</h2>
                  <div className="flex flex-col gap-2 mt-4">
                    <button className="btn btn-secondary" onClick={() => navigate(`/catalog/vehicles/${encodeURIComponent(String(id || ''))}/editar`)}>
                      Editar Veículo
                    </button>
                    <button className="btn btn-warning" onClick={onSoftDelete}>
                      Arquivar Veículo
                    </button>
                    <button className="btn btn-danger" onClick={onHardDelete}>
                      Excluir Permanentemente
                    </button>
                  </div>
                </div>
              )}

              <div className="card">
                <h2 className="card-header">Resumo</h2>
                <div className="mt-4 space-y-2 text-sm text-slate-700">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Preço</span>
                    <span className="font-semibold">{formatPrice(data.attributes?.price)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">KM</span>
                    <span className="font-semibold">
                      {data.attributes?.km != null ? new Intl.NumberFormat('pt-BR').format(data.attributes.km) : '—'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Marca/Modelo</span>
                    <span className="font-semibold">
                      {(data.attributes?.make || '—') + ' ' + (data.attributes?.model || '')}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
