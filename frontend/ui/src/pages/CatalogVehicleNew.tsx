import React, { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../lib/auth'

export default function CatalogVehicleNew() {
  const navigate = useNavigate()

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [createdId, setCreatedId] = useState<number | null>(null)

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

  const disableActions = useMemo(() => saving, [saving])

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

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setCreatedId(null)

    const missing: string[] = []
    if (!String(form.title || '').trim()) missing.push('título')
    if (missing.length) {
      setError(`Preencha os campos obrigatórios: ${missing.join(', ')}.`)
      return
    }

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

    try {
      setSaving(true)
      const res = await apiFetch('/api/admin/catalog/items', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_type_key: 'vehicle',
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
      const js = (await res.json()) as { id: number }
      setCreatedId(js.id)

      const urls = toImageUrls(form.imageUrls)
      const failed: string[] = []
      let hasInvalidImageUrl = false
      let hasUrlRequired = false
      for (const u of urls) {
        try {
          const mediaRes = await apiFetch(`/api/admin/catalog/items/${js.id}/media`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ kind: 'image', url: u }),
          })
          if (!mediaRes.ok) {
            const txt = await mediaRes.text().catch(() => '')
            if (txt.includes('invalid_image_url')) hasInvalidImageUrl = true
            if (txt.includes('url_required')) hasUrlRequired = true
            failed.push(u)
          }
        } catch {
          failed.push(u)
        }
      }

      if (failed.length) {
        if (hasUrlRequired) {
          setError(`Veículo criado (ID ${js.id}), mas você não informou a URL da imagem.`)
        } else if (hasInvalidImageUrl) {
          setError(
            `Veículo criado (ID ${js.id}), mas a URL informada não é uma imagem direta. ` +
              `Abra a foto no site do cliente e use "Copiar endereço da imagem" (precisa terminar em .jpg/.png/.webp).`
          )
        } else {
          setError(
            `Veículo criado (ID ${js.id}), mas falhou ao salvar ${failed.length} foto(s). ` +
              `Abra o veículo e tente adicionar as URLs novamente.`
          )
        }
        return
      }

      navigate(`/catalog/vehicles/${js.id}`)
    } catch (e: unknown) {
      const err = e as Error
      setError(err?.message || 'Erro ao salvar')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <Link
            to="/catalog/vehicles"
            className="inline-flex items-center gap-1 text-primary-600 hover:underline focus:outline-none focus:ring-2 focus:ring-primary-300 rounded px-1"
          >
            <span aria-hidden>←</span>
            <span>Voltar</span>
          </Link>
          <span className="text-slate-400">/</span>
          <span className="text-slate-800 font-medium">Cadastrar Veículo</span>
        </div>
      </header>

      {error && <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">{error}</div>}
      {createdId != null && (
        <div className="text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-3">
          <Link className="text-primary-600 hover:underline" to={`/catalog/vehicles/${encodeURIComponent(String(createdId))}`}>
            Abrir veículo criado (ID {createdId})
          </Link>
        </div>
      )}

      <form onSubmit={onSubmit} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <label className="block text-sm font-medium text-slate-700 mb-2">Título*</label>
            <input className="input" required value={form.title} onChange={(e) => upd('title', e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Ativo</label>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={!!form.is_active} onChange={(e) => upd('is_active', e.target.checked)} disabled={disableActions} />
              Ativo
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Preço (R$)</label>
            <input type="number" min="0" step="0.01" className="input" value={form.price} onChange={(e) => upd('price', e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Ano</label>
            <input type="number" min="1900" max="2100" step="1" className="input" value={form.year} onChange={(e) => upd('year', e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">KM</label>
            <input type="number" min="0" step="1" className="input" value={form.km} onChange={(e) => upd('km', e.target.value)} />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Marca</label>
            <input className="input" value={form.make} onChange={(e) => upd('make', e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Modelo</label>
            <input className="input" value={form.model} onChange={(e) => upd('model', e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Câmbio</label>
            <input className="input" value={form.transmission} onChange={(e) => upd('transmission', e.target.value)} />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Combustível</label>
            <input className="input" value={form.fuel} onChange={(e) => upd('fuel', e.target.value)} />
          </div>

          <div className="lg:col-span-3">
            <label className="block text-sm font-medium text-slate-700 mb-2">Descrição</label>
            <textarea className="input" rows={4} value={form.description} onChange={(e) => upd('description', e.target.value)} />
          </div>

          <div className="lg:col-span-3">
            <label className="block text-sm font-medium text-slate-700 mb-2">Acessórios (um por linha ou separados por vírgula)</label>
            <textarea className="input" rows={3} value={form.accessories} onChange={(e) => upd('accessories', e.target.value)} />
          </div>

          <div className="lg:col-span-3">
            <label className="block text-sm font-medium text-slate-700 mb-2">Fotos (URLs) — uma por linha</label>
            <textarea className="input" rows={3} value={form.imageUrls} onChange={(e) => upd('imageUrls', e.target.value)} />
            <div className="text-xs text-slate-500 mt-2">
              As fotos serão vinculadas ao veículo ao clicar em <span className="font-medium">Salvar</span>.
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <Link to="/catalog/vehicles" className="px-4 py-2 text-sm font-medium rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50">
            Cancelar
          </Link>
          <button type="submit" disabled={disableActions} className="px-4 py-2 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50">
            {saving ? 'Salvando...' : 'Salvar (inclui fotos)'}
          </button>
        </div>
      </form>
    </section>
  )
}
