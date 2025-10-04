import React, { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiFetch, isAuthenticated } from '../lib/auth'

interface ImovelDetalhesDTO {
  id: number
  titulo: string
  descricao?: string | null
  tipo: string
  finalidade: string
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
  imagens?: Array<{ id: number; url: string; is_capa: boolean; ordem: number }>
}

// Payload parcial (PATCH)
interface ImovelAtualizarDTO {
  titulo?: string
  descricao?: string
  preco?: number
  condominio?: number | null
  iptu?: number | null
  cidade?: string
  estado?: string
  bairro?: string | null
  endereco_json?: Record<string, any> | null
  dormitorios?: number | null
  banheiros?: number | null
  suites?: number | null
  vagas?: number | null
  area_total?: number | null
  area_util?: number | null
  ano_construcao?: number | null
  ativo?: boolean
}

export default function ImovelEditar() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [isAdmin, setIsAdmin] = useState(false)

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<ImovelDetalhesDTO | null>(null)

  // Form state (controlado)
  const [form, setForm] = useState<ImovelAtualizarDTO>({})
  const [showAdvanced, setShowAdvanced] = useState(false)

  function numOrNull(v: any): number | null {
    if (v === '' || v === undefined || v === null) return null
    const n = Number(v)
    return Number.isFinite(n) ? n : null
  }

  // Carrega detalhes para preencher o formulário
  useEffect(() => {
    let alive = true
    async function load() {
      if (!id) return
      setLoading(true)
      setError(null)
      try {
        const res = await apiFetch(`/api/re/imoveis/${encodeURIComponent(id)}/detalhes`, { cache: 'no-store' })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const js: ImovelDetalhesDTO = await res.json()
        if (!alive) return
        setData(js)
        setForm({
          titulo: js.titulo,
          descricao: js.descricao || '',
          preco: js.preco,
          cidade: js.cidade,
          estado: js.estado,
          bairro: js.bairro || '',
          dormitorios: js.dormitorios ?? null,
          banheiros: js.banheiros ?? null,
          suites: js.suites ?? null,
          vagas: js.vagas ?? null,
          area_total: js.area_total ?? null,
          area_util: js.area_util ?? null,
        })
      } catch (e: any) {
        if (alive) setError(e?.message || 'erro')
      } finally {
        if (alive) setLoading(false)
      }
    }
    // Descobre papel via backend
    async function loadRole() {
      try {
        if (!isAuthenticated()) { setIsAdmin(false); return }
        const me = await apiFetch('/api/auth/me')
        if (!me.ok) { setIsAdmin(false); return }
        const js = await me.json()
        setIsAdmin(js?.role === 'admin')
      } catch { setIsAdmin(false) }
    }
    // Carrega dados do imóvel base (para obter 'ativo')
    async function loadBase() {
      try {
        if (!id) return
        const res = await apiFetch(`/api/re/imoveis/${encodeURIComponent(id)}`)
        if (!res.ok) return
        const base = await res.json()
        setForm(prev => ({ ...prev, ativo: Boolean(base?.ativo) }))
      } catch {}
    }
    load()
    loadRole()
    loadBase()
    return () => { alive = false }
  }, [id])

  const disableActions = useMemo(() => saving || loading, [saving, loading])

  function onChange<K extends keyof ImovelAtualizarDTO>(key: K, value: ImovelAtualizarDTO[K]) {
    setForm(prev => ({ ...prev, [key]: value }))
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!id) return
    if (!isAdmin) {
      alert('Acesso restrito. Somente administradores podem editar.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      // Remove campos indefinidos para PATCH parcial
      const payload: Record<string, any> = {}
      Object.entries(form).forEach(([k, v]) => {
        if (v !== undefined) payload[k] = v
      })
      const res = await apiFetch(`/api/re/imoveis/${encodeURIComponent(id)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      navigate(`/imoveis/${encodeURIComponent(id)}`)
    } catch (e: any) {
      setError(e?.message || 'erro ao salvar')
    } finally {
      setSaving(false)
    }
  }

  if (!isAdmin) {
    return (
      <section className="space-y-4">
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-slate-600">
            <Link to="/imoveis" className="inline-flex items-center gap-1 text-primary-600 hover:underline">
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
          <Link to={`/imoveis/${encodeURIComponent(id || '')}`} className="inline-flex items-center gap-1 text-primary-600 hover:underline focus:outline-none focus:ring-2 focus:ring-primary-300 rounded px-1">
            <span aria-hidden>←</span>
            <span>Voltar</span>
          </Link>
          <span className="text-slate-400">/</span>
          <span className="text-slate-800 font-medium">Editar Imóvel</span>
        </div>
      </header>

      {loading && <div className="text-sm text-gray-600">Carregando...</div>}
      {error && <div className="text-sm text-red-600">Erro: {error}</div>}

      {!loading && (
        <form onSubmit={onSubmit} className="space-y-6">
          {/* Básico */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-600 mb-1">Título</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={form.titulo || ''} onChange={(e) => onChange('titulo', e.target.value)} required />
            </div>
            <div>
              <label className="block text-xs text-slate-600 mb-1">Preço (R$)</label>
              <input type="number" step="0.01" className="w-full border rounded px-3 py-2 text-sm" value={form.preco ?? 0} onChange={(e) => onChange('preco', Number(e.target.value))} min={0} />
            </div>
            <div>
              <label className="block text-xs text-slate-600 mb-1">Cidade</label>
              <input className="w-full border rounded px-3 py-2 text-sm" value={form.cidade || ''} onChange={(e) => onChange('cidade', e.target.value)} required />
            </div>
            <div>
              <label className="block text-xs text-slate-600 mb-1">Estado (UF)</label>
              <input className="w-full border rounded px-3 py-2 text-sm uppercase" value={form.estado || ''} onChange={(e) => onChange('estado', e.target.value.toUpperCase())} maxLength={2} required />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs text-slate-600 mb-1">Descrição</label>
              <textarea className="w-full border rounded px-3 py-2 text-sm" rows={4} value={form.descricao || ''} onChange={(e) => onChange('descricao', e.target.value)} />
            </div>
          </div>

          {/* Status e básico extra */}
          <div className="flex items-center gap-4">
            <label className="inline-flex items-center gap-2 text-sm">
              <input type="checkbox" checked={!!form.ativo} onChange={(e) => onChange('ativo', e.target.checked)} />
              <span>Ativo</span>
            </label>
            <div className="text-xs text-slate-500">ID: {data?.id}</div>
          </div>

          {/* Avançado (colapsável) */}
          <div className="space-y-3">
            <button type="button" onClick={() => setShowAdvanced(v => !v)} className="text-xs px-3 py-1 rounded border">
              {showAdvanced ? 'Ocultar avançado' : 'Mostrar avançado'}
            </button>
            {showAdvanced && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs text-slate-600 mb-1">Bairro</label>
                  <input className="w-full border rounded px-3 py-2 text-sm" value={(form.bairro as any) || ''} onChange={(e) => onChange('bairro', e.target.value)} />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">Dormitórios</label>
                  <input type="number" min={0} className="w-full border rounded px-3 py-2 text-sm" value={form.dormitorios ?? ''} onChange={(e) => onChange('dormitorios', numOrNull(e.target.value))} />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">Banheiros</label>
                  <input type="number" min={0} className="w-full border rounded px-3 py-2 text-sm" value={form.banheiros ?? ''} onChange={(e) => onChange('banheiros', numOrNull(e.target.value))} />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">Suítes</label>
                  <input type="number" min={0} className="w-full border rounded px-3 py-2 text-sm" value={form.suites ?? ''} onChange={(e) => onChange('suites', numOrNull(e.target.value))} />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">Vagas</label>
                  <input type="number" min={0} className="w-full border rounded px-3 py-2 text-sm" value={form.vagas ?? ''} onChange={(e) => onChange('vagas', numOrNull(e.target.value))} />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">Área total (m²)</label>
                  <input type="number" min={0} step="0.01" className="w-full border rounded px-3 py-2 text-sm" value={form.area_total ?? ''} onChange={(e) => onChange('area_total', numOrNull(e.target.value))} />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">Área útil (m²)</label>
                  <input type="number" min={0} step="0.01" className="w-full border rounded px-3 py-2 text-sm" value={form.area_util ?? ''} onChange={(e) => onChange('area_util', numOrNull(e.target.value))} />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">Condomínio (R$)</label>
                  <input type="number" min={0} step="0.01" className="w-full border rounded px-3 py-2 text-sm" value={form.condominio ?? ''} onChange={(e) => onChange('condominio', numOrNull(e.target.value))} />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">IPTU (R$)</label>
                  <input type="number" min={0} step="0.01" className="w-full border rounded px-3 py-2 text-sm" value={form.iptu ?? ''} onChange={(e) => onChange('iptu', numOrNull(e.target.value))} />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 mb-1">Ano de construção</label>
                  <input type="number" min={1800} max={new Date().getFullYear() + 1} className="w-full border rounded px-3 py-2 text-sm" value={form.ano_construcao ?? ''} onChange={(e) => onChange('ano_construcao', numOrNull(e.target.value))} />
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center justify-between">
            <div className="text-xs text-slate-500">ID: {data?.id}</div>
            <div className="flex gap-2">
              <button type="button" className="px-3 py-2 rounded border text-sm" onClick={() => navigate(-1)} disabled={disableActions}>Cancelar</button>
              <button type="submit" className="px-3 py-2 rounded bg-blue-600 text-white text-sm disabled:opacity-50" disabled={disableActions}>{saving ? 'Salvando...' : 'Salvar'}</button>
            </div>
          </div>
        </form>
      )}
    </section>
  )
}
