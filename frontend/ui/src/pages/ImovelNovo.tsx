import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'

export default function ImovelNovo() {
  const navigate = useNavigate()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [form, setForm] = useState({
    titulo: '',
    descricao: '',
    tipo: 'apartment',
    finalidade: 'sale',
    preco: '',
    condominio: '',
    iptu: '',
    cidade: '',
    estado: '',
    bairro: '',
    dormitorios: '',
    banheiros: '',
    suites: '',
    vagas: '',
    area_total: '',
    area_util: '',
    ano_construcao: '',
  })
  const [files, setFiles] = useState<File[]>([])
  const MAX_FILES = 10

  function upd<K extends keyof typeof form>(k: K, v: (typeof form)[K]) {
    setForm(prev => ({ ...prev, [k]: v }))
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    // Validações mínimas e mensagens
    const missing: string[] = []
    if (!form.titulo) missing.push('título')
    if (!form.tipo) missing.push('tipo')
    if (!form.finalidade) missing.push('finalidade')
    if (!form.preco) missing.push('preço')
    if (!form.cidade) missing.push('cidade')
    if (!form.estado) missing.push('estado')
    if (missing.length) {
      setError(`Preencha os campos obrigatórios: ${missing.join(', ')}.`)
      return
    }
    if (String(form.estado).length !== 2) {
      setError('Estado (UF) deve ter 2 letras, ex.: SP')
      return
    }
    const precoNum = Number(form.preco)
    if (!Number.isFinite(precoNum) || precoNum <= 0) {
      setError('Preço deve ser um número maior que zero.')
      return
    }
    const payload: Record<string, unknown> = {
      titulo: form.titulo,
      descricao: form.descricao || null,
      tipo: form.tipo,
      finalidade: form.finalidade,
      preco: Number(form.preco),
      condominio: form.condominio ? Number(form.condominio) : null,
      iptu: form.iptu ? Number(form.iptu) : null,
      cidade: form.cidade,
      estado: form.estado.toUpperCase(),
      bairro: form.bairro || null,
      endereco_json: null,
      dormitorios: form.dormitorios ? Number(form.dormitorios) : null,
      banheiros: form.banheiros ? Number(form.banheiros) : null,
      suites: form.suites ? Number(form.suites) : null,
      vagas: form.vagas ? Number(form.vagas) : null,
      area_total: form.area_total ? Number(form.area_total) : null,
      area_util: form.area_util ? Number(form.area_util) : null,
      ano_construcao: form.ano_construcao ? Number(form.ano_construcao) : null,
    }
    try {
      setSaving(true)
      const res = await fetch('/api/re/imoveis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const js = await res.json()
      // Upload de imagens (opcional)
      if (files.length) {
        const toSend = files.slice(0, MAX_FILES)
        const fd = new FormData()
        toSend.forEach(f => fd.append('files', f))
        const up = await fetch(`/api/re/imoveis/${js.id}/imagens/upload`, {
          method: 'POST',
          body: fd,
        })
        if (!up.ok) {
          console.error('Falha no upload de imagens', await up.text())
        }
      }
      navigate(`/imoveis/${js.id}`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erro ao salvar'
      setError(msg)
    } finally {
      setSaving(false)
    }
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
          <span className="text-slate-800 font-medium">Cadastrar Imóvel</span>
        </div>
      </header>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">{error}</div>
      )}

      <form onSubmit={onSubmit} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Título*</label>
            <input className="input" placeholder="Ex.: Apto 2 dorm – Centro" aria-label="Título do imóvel" required value={form.titulo} onChange={e => upd('titulo', e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Tipo*</label>
            <select className="select" aria-label="Tipo do imóvel" required value={form.tipo} onChange={e => upd('tipo', e.target.value)}>
              <option value="apartment">Apartamento</option>
              <option value="house">Casa</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Finalidade*</label>
            <select className="select" aria-label="Finalidade" required value={form.finalidade} onChange={e => upd('finalidade', e.target.value)}>
              <option value="sale">Venda</option>
              <option value="rent">Locação</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Preço (R$)*</label>
            <input type="number" min="0" step="0.01" className="input" placeholder="Ex.: 3200" aria-label="Preço em reais" required value={form.preco} onChange={e => upd('preco', e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Condomínio (R$)</label>
            <input type="number" min="0" step="0.01" className="input" placeholder="Ex.: 550" aria-label="Condomínio" value={form.condominio} onChange={e => upd('condominio', e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">IPTU (R$)</label>
            <input type="number" min="0" step="0.01" className="input" placeholder="Ex.: 120" aria-label="IPTU" value={form.iptu} onChange={e => upd('iptu', e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Cidade*</label>
            <input className="input" placeholder="Ex.: Mogi das Cruzes" aria-label="Cidade" required value={form.cidade} onChange={e => upd('cidade', e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Estado (UF)*</label>
            <input maxLength={2} className="input" placeholder="SP" aria-label="Estado (UF)" required value={form.estado} onChange={e => upd('estado', e.target.value.toUpperCase())} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Bairro</label>
            <input className="input" placeholder="Ex.: Centro" aria-label="Bairro" value={form.bairro} onChange={e => upd('bairro', e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Dormitórios</label>
            <input type="number" min="0" step="1" className="input" placeholder="Ex.: 2" aria-label="Dormitórios" value={form.dormitorios} onChange={e => upd('dormitorios', e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Banheiros</label>
            <input type="number" min="0" step="1" className="input" placeholder="Ex.: 1" aria-label="Banheiros" value={form.banheiros} onChange={e => upd('banheiros', e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Suítes</label>
            <input type="number" min="0" step="1" className="input" placeholder="Ex.: 1" aria-label="Suítes" value={form.suites} onChange={e => upd('suites', e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Vagas</label>
            <input type="number" min="0" step="1" className="input" placeholder="Ex.: 1" aria-label="Vagas" value={form.vagas} onChange={e => upd('vagas', e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Área total (m²)</label>
            <input type="number" min="0" step="0.01" className="input" placeholder="Ex.: 65" aria-label="Área total" value={form.area_total} onChange={e => upd('area_total', e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Área útil (m²)</label>
            <input type="number" min="0" step="0.01" className="input" placeholder="Ex.: 60" aria-label="Área útil" value={form.area_util} onChange={e => upd('area_util', e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Ano de construção</label>
            <input type="number" min="1800" max="2100" step="1" className="input" placeholder="Ex.: 2015" aria-label="Ano de construção" value={form.ano_construcao} onChange={e => upd('ano_construcao', e.target.value)} />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">Descrição</label>
          <textarea className="input" rows={4} placeholder="Destaques do imóvel" aria-label="Descrição" value={form.descricao} onChange={e => upd('descricao', e.target.value)} />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">Imagens (até {MAX_FILES})</label>
          <input type="file" multiple accept="image/jpeg,image/png,image/webp" onChange={e => {
            const selected = Array.from(e.target.files || [])
            const limited = selected.slice(0, MAX_FILES)
            setFiles(limited)
          }} />
          {files.length > 0 && (
            <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-2">
              {files.map((f, i) => (
                <div key={i} className="border border-slate-200 rounded-lg p-1 text-center">
                  <img src={URL.createObjectURL(f)} alt={f.name} className="w-full h-24 object-cover rounded" />
                  <div className="mt-1 text-[11px] text-slate-600 truncate" title={f.name}>{f.name}</div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="flex justify-end gap-3">
          <Link to="/imoveis" className="px-4 py-2 text-sm font-medium rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50">Cancelar</Link>
          <button type="submit" disabled={saving} className="px-4 py-2 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50">
            {saving ? 'Salvando...' : 'Salvar'}
          </button>
        </div>
      </form>
    </section>
  )
}
