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

interface CatalogItem {
  id: number
  title: string
  description?: string | null
  attributes: VehicleAttributes
  is_active: boolean
}

interface CatalogMedia {
  id: number
  item_id: number
  kind: string
  url: string
  sort_order: number
}

export default function CatalogVehicleEdit() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [isAdmin, setIsAdmin] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [data, setData] = useState<CatalogItem | null>(null)
  const [media, setMedia] = useState<CatalogMedia[]>([])
  const [failedMediaIds, setFailedMediaIds] = useState<Set<number>>(new Set())
  const [form, setForm] = useState({
    title: '',
    description: '',
    price: '',
    year: '',
    km: '',
    make: '',
    model: '',
    transmission: '',
    fuel: '',
    accessories: '',
    imageUrls: '',
    is_active: true,
  })

  const disableActions = useMemo(() => saving || loading, [saving, loading])

  function upd<K extends keyof typeof form>(k: K, v: (typeof form)[K]) {
    setForm((prev) => ({ ...prev, [k]: v }))
  }

  function toNumOrUndefined(v: string): number | undefined {
    const s = String(v || '').trim()
    if (!s) return undefined
    const n = Number(s)
    return Number.isFinite(n) ? n : undefined
  }

  function toAccessoriesList(raw: string): string[] {
    const s = String(raw || '').trim()
    if (!s) return []
    const parts = s
      .split(/\r?\n|,/g)
      .map((x) => String(x || '').trim())
      .filter(Boolean)
    const out: string[] = []
    const seen = new Set<string>()
    for (const p of parts) {
      const k = p.toLowerCase()
      if (seen.has(k)) continue
      seen.add(k)
      out.push(p)
    }
    return out.slice(0, 40)
  }

  function toImageUrls(raw: string): string[] {
    const s = String(raw || '').trim()
    if (!s) return []
    const parts = s
      .split(/\r?\n/g)
      .map((x) => String(x || '').trim())
      .filter(Boolean)
    const out: string[] = []
    const seen = new Set<string>()
    for (const p of parts) {
      if (seen.has(p)) continue
      seen.add(p)
      out.push(p)
    }
    return out.slice(0, 15)
  }

  async function loadMedia(itemId: string) {
    try {
      const res = await apiFetch(`/api/admin/catalog/items/${encodeURIComponent(itemId)}/media`, { cache: 'no-store' })
      if (!res.ok) return
      const js = (await res.json()) as CatalogMedia[]
      setMedia(Array.isArray(js) ? js : [])
      setFailedMediaIds(new Set())
    } catch {
      // ignore
    }
  }

  async function addMediaUrls(itemId: string, raw: string) {
    const urls = toImageUrls(raw)
    if (!urls.length) return
    const failed: string[] = []
    let hasInvalidImageUrl = false
    let hasUrlRequired = false
    for (const u of urls) {
      try {
        const res = await apiFetch(`/api/admin/catalog/items/${encodeURIComponent(itemId)}/media`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind: 'image', url: u }),
        })
        if (!res.ok) {
          const txt = await res.text().catch(() => '')
          if (txt.includes('invalid_image_url')) hasInvalidImageUrl = true
          if (txt.includes('url_required')) hasUrlRequired = true
          failed.push(u)
        }
      } catch {
        failed.push(u)
      }
    }
    await loadMedia(itemId)
    if (failed.length) {
      if (hasUrlRequired) {
        setError('Informe a URL da imagem.')
      } else if (hasInvalidImageUrl) {
        setError(
          'A URL informada não é uma imagem direta. ' +
            'Abra a foto no site do cliente e use "Copiar endereço da imagem" (precisa terminar em .jpg/.png/.webp).'
        )
      } else {
        setError(`Falhou ao salvar ${failed.length} foto(s). Verifique as URLs e tente novamente.`)
      }
    } else {
      upd('imageUrls', '')
    }
  }

  async function deleteMedia(mediaId: number) {
    if (!id) return
    try {
      const res = await apiFetch(`/api/admin/catalog/media/${encodeURIComponent(String(mediaId))}`, { method: 'DELETE' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await loadMedia(String(id))
    } catch (e: unknown) {
      const err = e as Error
      setError(err?.message || 'Erro ao remover imagem')
    }
  }

  useEffect(() => {
    let alive = true

    async function loadRole() {
      try {
        if (!isAuthenticated()) {
          if (alive) setIsAdmin(false)
          return
        }
        const res = await apiFetch('/api/auth/me')
        if (!res.ok) {
          if (alive) setIsAdmin(false)
          return
        }
        const js = await res.json()
        if (alive) setIsAdmin(js?.role === 'admin')
      } catch {
        if (alive) setIsAdmin(false)
      }
    }

    async function load() {
      if (!id) return
      setLoading(true)
      setError(null)
      try {
        const res = await apiFetch(`/api/admin/catalog/items/${encodeURIComponent(id)}`, { cache: 'no-store' })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const js = (await res.json()) as CatalogItem
        if (!alive) return
        setData(js)

        const a = js.attributes || {}
        setForm({
          title: js.title || '',
          description: js.description || '',
          price: a.price != null ? String(a.price) : '',
          year: a.year != null ? String(a.year) : '',
          km: a.km != null ? String(a.km) : '',
          make: a.make || '',
          model: a.model || '',
          transmission: a.transmission || '',
          fuel: a.fuel || '',
          accessories: Array.isArray(a.accessories) ? a.accessories.join('\n') : '',
          imageUrls: '',
          is_active: !!js.is_active,
        })

        await loadMedia(String(id))
      } catch (e: unknown) {
        const err = e as Error
        if (alive) setError(err?.message || 'erro')
      } finally {
        if (alive) setLoading(false)
      }
    }

    void loadRole()
    void load()
    return () => {
      alive = false
    }
  }, [id])

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!id) return
    if (!isAdmin) {
      window.alert('Acesso restrito. É necessário ser administrador.')
      return
    }

    setSaving(true)
    setError(null)
    try {
      const attributes: Record<string, unknown> = {}
      const price = toNumOrUndefined(form.price)
      const year = toNumOrUndefined(form.year)
      const km = toNumOrUndefined(form.km)
      if (price != null) attributes.price = price
      if (year != null) attributes.year = year
      if (km != null) attributes.km = km
      if (String(form.make || '').trim()) attributes.make = String(form.make).trim()
      if (String(form.model || '').trim()) attributes.model = String(form.model).trim()
      if (String(form.transmission || '').trim()) attributes.transmission = String(form.transmission).trim()
      if (String(form.fuel || '').trim()) attributes.fuel = String(form.fuel).trim()

      const accessories = toAccessoriesList(form.accessories)
      if (accessories.length) attributes.accessories = accessories

      const res = await apiFetch(`/api/admin/catalog/items/${encodeURIComponent(id)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: String(form.title || '').trim(),
          description: String(form.description || '').trim() || null,
          attributes,
          is_active: !!form.is_active,
        }),
      })
      if (!res.ok) {
        const txt = await res.text().catch(() => '')
        throw new Error(txt || `HTTP ${res.status}`)
      }

      await addMediaUrls(String(id), form.imageUrls)
      navigate(`/catalog/vehicles/${encodeURIComponent(id)}`)
    } catch (e: unknown) {
      const err = e as Error
      setError(err?.message || 'erro ao salvar')
    } finally {
      setSaving(false)
    }
  }

  if (!isAdmin) {
    return (
      <section className="space-y-4">
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-slate-600">
            <Link to="/catalog/vehicles" className="inline-flex items-center gap-1 text-primary-600 hover:underline">
              <span aria-hidden>←</span>
              <span>Voltar</span>
            </Link>
          </div>
        </header>
        <div className="text-red-600 text-sm">Acesso restrito. É necessário ser administrador.</div>
      </section>
    )
  }

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <Link
            to={`/catalog/vehicles/${encodeURIComponent(String(id || ''))}`}
            className="inline-flex items-center gap-1 text-primary-600 hover:underline focus:outline-none focus:ring-2 focus:ring-primary-300 rounded px-1"
          >
            <span aria-hidden>←</span>
            <span>Voltar</span>
          </Link>
          <span className="text-slate-400">/</span>
          <span className="text-slate-800 font-medium">Editar Veículo</span>
        </div>
      </header>

      {loading && <div className="text-sm text-gray-600">Carregando...</div>}
      {error && <div className="text-sm text-red-600">Erro: {error}</div>}

      {!loading && data && (
        <form onSubmit={onSubmit} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-2">Título*</label>
              <input className="input" required value={form.title} onChange={(e) => upd('title', e.target.value)} disabled={disableActions} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Ativo</label>
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input type="checkbox" checked={!!form.is_active} onChange={(e) => upd('is_active', e.target.checked)} disabled={disableActions} />
                Ativo
              </label>
              <div className="text-xs text-slate-500 mt-2">ID: {data.id}</div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Preço (R$)</label>
              <input type="number" min="0" step="0.01" className="input" value={form.price} onChange={(e) => upd('price', e.target.value)} disabled={disableActions} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Ano</label>
              <input type="number" min="1900" max="2100" step="1" className="input" value={form.year} onChange={(e) => upd('year', e.target.value)} disabled={disableActions} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">KM</label>
              <input type="number" min="0" step="1" className="input" value={form.km} onChange={(e) => upd('km', e.target.value)} disabled={disableActions} />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Marca</label>
              <input className="input" value={form.make} onChange={(e) => upd('make', e.target.value)} disabled={disableActions} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Modelo</label>
              <input className="input" value={form.model} onChange={(e) => upd('model', e.target.value)} disabled={disableActions} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Câmbio</label>
              <input className="input" value={form.transmission} onChange={(e) => upd('transmission', e.target.value)} disabled={disableActions} />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Combustível</label>
              <input className="input" value={form.fuel} onChange={(e) => upd('fuel', e.target.value)} disabled={disableActions} />
            </div>

            <div className="lg:col-span-3">
              <label className="block text-sm font-medium text-slate-700 mb-2">Descrição</label>
              <textarea className="input" rows={4} value={form.description} onChange={(e) => upd('description', e.target.value)} disabled={disableActions} />
            </div>

            <div className="lg:col-span-3">
              <label className="block text-sm font-medium text-slate-700 mb-2">Acessórios (um por linha ou separados por vírgula)</label>
              <textarea className="input" rows={3} value={form.accessories} onChange={(e) => upd('accessories', e.target.value)} disabled={disableActions} />
            </div>

            <div className="lg:col-span-3">
              <label className="block text-sm font-medium text-slate-700 mb-2">Fotos atuais</label>
              {media.length ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                  {media
                    .filter((m) => m.kind === 'image' && !!m.url)
                    .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
                    .map((m) => (
                      <div key={m.id} className="border border-slate-200 rounded-lg overflow-hidden bg-white">
                        <div className="aspect-[4/3] bg-slate-100">
                          {!failedMediaIds.has(m.id) ? (
                            <img
                              src={m.url}
                              alt=""
                              className="w-full h-full object-cover"
                              loading="lazy"
                              onError={() => {
                                setFailedMediaIds((prev) => {
                                  const next = new Set(prev)
                                  next.add(m.id)
                                  return next
                                })
                              }}
                            />
                          ) : (
                            <div className="w-full h-full flex flex-col items-center justify-center text-slate-500 text-xs p-2 text-center">
                              <div>Falha ao carregar</div>
                              <a
                                href={m.url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-primary-600 hover:underline mt-1"
                              >
                                Abrir URL
                              </a>
                            </div>
                          )}
                        </div>
                        <div className="p-2">
                          <a
                            href={m.url}
                            target="_blank"
                            rel="noreferrer"
                            className="block text-[11px] text-slate-500 hover:text-slate-700 hover:underline truncate"
                            title={m.url}
                          >
                            {m.url}
                          </a>
                          <button
                            type="button"
                            className="w-full text-xs px-2 py-1 rounded-md border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50 mt-2"
                            disabled={disableActions}
                            onClick={() => void deleteMedia(m.id)}
                          >
                            Remover
                          </button>
                        </div>
                      </div>
                    ))}
                </div>
              ) : (
                <div className="text-xs text-slate-500">Nenhuma foto cadastrada.</div>
              )}
            </div>

            <div className="lg:col-span-3">
              <label className="block text-sm font-medium text-slate-700 mb-2">Adicionar fotos (URLs) — uma por linha</label>
              <textarea className="input" rows={3} value={form.imageUrls} onChange={(e) => upd('imageUrls', e.target.value)} disabled={disableActions} />
              <div className="flex justify-end mt-2">
                <button
                  type="button"
                  disabled={disableActions || !String(form.imageUrls || '').trim()}
                  className="text-xs px-3 py-2 rounded-lg bg-slate-200 text-slate-800 hover:bg-slate-300 disabled:opacity-50"
                  onClick={() => {
                    if (!id) return
                    void addMediaUrls(String(id), form.imageUrls)
                  }}
                >
                  Adicionar URLs
                </button>
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <Link
              to={`/catalog/vehicles/${encodeURIComponent(String(id || ''))}`}
              className="px-4 py-2 text-sm font-medium rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
            >
              Cancelar
            </Link>
            <button type="submit" disabled={disableActions} className="px-4 py-2 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50">
              {saving ? 'Salvando...' : 'Salvar'}
            </button>
          </div>
        </form>
      )}
    </section>
  )
}
