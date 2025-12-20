import React, { useEffect, useState } from 'react'

interface Lead {
  id: number
  name?: string | null
  phone?: string | null
  email?: string | null
  source?: string | null
  status?: string | null
  preferences?: Record<string, unknown> | null
  property_interest_id?: number | null
  external_property_id?: string | null
  last_inbound_at?: string | null
  created_at?: string | null
  finalidade?: string | null
  tipo?: string | null
  cidade?: string | null
  preco_min?: number | null
  preco_max?: number | null
}

interface Visit {
  id: number
  lead_id: number
  property_id: number
  status: string
  scheduled_datetime?: string | null
}

interface Filters {
  search: string
  status: string
  dateFrom: string
  dateTo: string
  codigoImovel: string
  finalidade: string
  tipo: string
  cidade: string
  valorMin: string
  valorMax: string
}

export default function LeadsList() {
  const [data, setData] = useState<Lead[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showFilters, setShowFilters] = useState(false)
  const [filters, setFilters] = useState<Filters>({
    search: '',
    status: '',
    dateFrom: '',
    dateTo: '',
    codigoImovel: '',
    finalidade: '',
    tipo: '',
    cidade: '',
    valorMin: '',
    valorMax: ''
  })

  const [stats, setStats] = useState({
    total: 0,
    iniciados: 0,
    novos: 0,
    qualificados: 0,
    pendentes: 0,
    agendados: 0,
    sem_imovel: 0
  })

  const [visits, setVisits] = useState<Visit[]>([])
  const [showConfigModal, setShowConfigModal] = useState(false)
  const [recipients, setRecipients] = useState<string[]>([])
  const [template, setTemplate] = useState<string>('')
  const [confirmingVisitId, setConfirmingVisitId] = useState<number | null>(null)

  useEffect(() => {
    loadLeads()
    loadConfig()
  }, [])

  async function loadLeads() {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/re/leads?limit=200', { cache: 'no-store' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const leads: Lead[] = await res.json()
      setData(leads)
      
      // Calcular estatísticas
      setStats({
        total: leads.length,
        iniciados: leads.filter((l: Lead) => l.status === 'iniciado').length,
        novos: leads.filter((l: Lead) => l.status === 'novo').length,
        qualificados: leads.filter((l: Lead) => l.status === 'qualificado').length,
        pendentes: leads.filter((l: Lead) => l.status === 'agendamento_pendente').length,
        agendados: leads.filter((l: Lead) => l.status === 'agendado').length,
        sem_imovel: leads.filter((l: Lead) => l.status === 'sem_imovel_disponivel').length
      })

      // Carregar visitas pendentes
      try {
        const visRes = await fetch('/api/admin/re/visits?status=requested&limit=50', { cache: 'no-store' })
        if (visRes.ok) {
          const visData: Visit[] = await visRes.json()
          setVisits(visData)
        }
      } catch {
        // Silenciar erro de visitas
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'erro')
    } finally {
      setLoading(false)
    }
  }

  async function loadConfig() {
    try {
      const token = localStorage.getItem('auth_token')
      const headers: Record<string, string> = {}
      if (token) headers['Authorization'] = `Bearer ${token}`

      const recRes = await fetch('/api/admin/re/booking/recipients', { headers, cache: 'no-store' })
      if (recRes.ok) {
        const rec = await recRes.json()
        if (rec?.recipients) setRecipients(rec.recipients)
      }
      const tplRes = await fetch('/api/admin/re/booking/template', { headers, cache: 'no-store' })
      if (tplRes.ok) {
        const tpl = await tplRes.json()
        if (typeof tpl?.template_name === 'string') setTemplate(tpl.template_name)
      }
    } catch {
      // silencioso
    }
  }

  const filteredData = data?.filter(lead => {
    // Busca geral (nome, telefone, email)
    if (filters.search) {
      const search = filters.search.toLowerCase()
      const matchName = lead.name?.toLowerCase().includes(search)
      const matchPhone = lead.phone?.toLowerCase().includes(search)
      const matchEmail = lead.email?.toLowerCase().includes(search)
      if (!matchName && !matchPhone && !matchEmail) return false
    }

    // Filtro de status
    if (filters.status && lead.status !== filters.status) return false

    // Filtro de código do imóvel (ex: A738)
    if (filters.codigoImovel) {
      const codigo = filters.codigoImovel.toUpperCase()
      const leadCodigo = (lead.external_property_id || '').toUpperCase()
      if (!leadCodigo.includes(codigo)) return false
    }

    // Filtros de preferências (buscar nos campos diretos do lead, não em preferences)
    if (filters.finalidade) {
      const leadFinalidade = lead.finalidade
      if (leadFinalidade !== filters.finalidade) return false
    }
    if (filters.tipo) {
      const leadTipo = lead.tipo
      if (leadTipo !== filters.tipo) return false
    }
    if (filters.cidade) {
      const leadCidade = lead.cidade
      if (!leadCidade?.toLowerCase().includes(filters.cidade.toLowerCase())) return false
    }
    
    if (filters.valorMin) {
      const leadPrecoMax = lead.preco_max
      if (leadPrecoMax && leadPrecoMax < parseFloat(filters.valorMin)) return false
    }
    if (filters.valorMax) {
      const leadPrecoMin = lead.preco_min
      if (leadPrecoMin && leadPrecoMin > parseFloat(filters.valorMax)) return false
    }

    // Filtro de data
    if (filters.dateFrom && lead.last_inbound_at) {
      if (lead.last_inbound_at < filters.dateFrom) return false
    }
    if (filters.dateTo && lead.last_inbound_at) {
      if (lead.last_inbound_at > filters.dateTo + 'T23:59:59') return false
    }

    return true
  })

  // Ordenação client-side (não quebra API): status prioritário > última atividade > id desc
  const statusOrder: Record<string, number> = {
    agendamento_pendente: 1,
    agendado: 2,
    qualificado: 3,
    novo: 4,
    iniciado: 5,
    sem_imovel_disponivel: 6,
    direcionado: 7,
  }
  const sortedData = [...(filteredData || [])].sort((a, b) => {
    const ra = statusOrder[(a.status || '').toLowerCase()] ?? 99
    const rb = statusOrder[(b.status || '').toLowerCase()] ?? 99
    if (ra !== rb) return ra - rb
    const da = a.last_inbound_at ? new Date(a.last_inbound_at).getTime() : 0
    const db = b.last_inbound_at ? new Date(b.last_inbound_at).getTime() : 0
    if (db !== da) return db - da
    return (b.id || 0) - (a.id || 0)
  })

  function clearFilters() {
    setFilters({
      search: '',
      status: '',
      dateFrom: '',
      dateTo: '',
      codigoImovel: '',
      finalidade: '',
      tipo: '',
      cidade: '',
      valorMin: '',
      valorMax: ''
    })
  }

  const hasActiveFilters = Object.values(filters).some(v => v !== '')

  function getStatusBadge(status?: string | null) {
    const statusMap: Record<string, { label: string; color: string }> = {
      novo: { label: 'Novo', color: 'bg-blue-100 text-blue-800' },
      qualificado: { label: 'Qualificado', color: 'bg-green-100 text-green-800' },
      agendado: { label: 'Agendado', color: 'bg-purple-100 text-purple-800' },
      agendamento_pendente: { label: 'Pendente', color: 'bg-red-100 text-red-800' },
      sem_imovel_disponivel: { label: 'Sem Imóvel', color: 'bg-orange-100 text-orange-800' },
      direcionado: { label: 'Direcionado', color: 'bg-yellow-100 text-yellow-800' },
      iniciado: { label: 'Iniciado', color: 'bg-slate-100 text-slate-800' }
    }
    const s = statusMap[status || 'novo'] || { label: status || 'Novo', color: 'bg-slate-100 text-slate-800' }
    return <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${s.color}`}>{s.label}</span>
  }

  function formatDate(date?: string | null) {
    if (!date) return '-'
    const d = new Date(date)
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
  }

  function formatPrice(price?: number | null) {
    if (price === null || price === undefined) return '-'
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(price)
  }

  // Formata telefone removendo @c.us e aplicando máscara brasileira
  function formatPhone(phone?: string | null) {
    if (!phone) return '-'
    const cleaned = String(phone).replace(/@c\.us$/i, '')
    const digits = cleaned.replace(/\D/g, '')
    if (!digits) return cleaned
    let country = '', area = '', local = digits
    if (digits.startsWith('55') && digits.length >= 12) {
      country = '+55 '
      area = `(${digits.slice(2, 4)}) `
      local = digits.slice(4)
    } else if (digits.length === 11) {
      area = `(${digits.slice(0, 2)}) `
      local = digits.slice(2)
    } else if (digits.length === 10) {
      area = `(${digits.slice(0, 2)}) `
      local = digits.slice(2)
    }
    let formatted = local
    if (local.length >= 9) {
      formatted = `${local.slice(0, 5)}-${local.slice(5, 9)}`
    } else if (local.length === 8) {
      formatted = `${local.slice(0, 4)}-${local.slice(4, 8)}`
    }
    return `${country}${area}${formatted}`.trim()
  }

  return (
    <section className="space-y-6">
      {/* Header */}
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Gestão de Leads</h1>
          <p className="text-sm text-slate-600 mt-1">Gerencie e acompanhe todos os seus leads</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowConfigModal(true)}
            className="px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors text-sm font-medium"
          >
            ⚙️ Configurar notificações
          </button>
          <button
            onClick={loadLeads}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors text-sm font-medium"
          >
            🔄 Atualizar
          </button>
        </div>
      </header>

      {/* Stats Cards */}
      <div className="overflow-x-auto pb-2">
        <div className="grid grid-cols-[repeat(7,minmax(0,1fr))] gap-4 min-w-[1120px]">
          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-600">Total de Leads</p>
                <p className="text-3xl font-bold text-slate-900 mt-2">{stats.total}</p>
              </div>
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center text-2xl">
                👥
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-600">Iniciados</p>
                <p className="text-3xl font-bold text-slate-900 mt-2">{stats.iniciados}</p>
              </div>
              <div className="w-12 h-12 bg-slate-100 rounded-lg flex items-center justify-center text-2xl">
                🟦
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-600">Novos</p>
                <p className="text-3xl font-bold text-blue-600 mt-2">{stats.novos}</p>
              </div>
              <div className="w-12 h-12 bg-blue-50 rounded-lg flex items-center justify-center text-2xl">
                🆕
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-green-600">Qualificados</p>
                <p className="text-3xl font-bold text-green-600 mt-2">{stats.qualificados}</p>
              </div>
              <div className="w-12 h-12 bg-green-50 rounded-lg flex items-center justify-center text-2xl">
                ✅
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-red-600">⚠️ Pendentes</p>
                <p className="text-3xl font-bold text-red-600 mt-2">{stats.pendentes}</p>
              </div>
              <div className="w-12 h-12 bg-red-50 rounded-lg flex items-center justify-center text-2xl">
                ⏳
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-purple-600">Agendados</p>
                <p className="text-3xl font-bold text-purple-600 mt-2">{stats.agendados}</p>
              </div>
              <div className="w-12 h-12 bg-purple-50 rounded-lg flex items-center justify-center text-2xl">
                📅
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-orange-600">Sem Imóvel</p>
                <p className="text-3xl font-bold text-orange-600 mt-2">{stats.sem_imovel}</p>
              </div>
              <div className="w-12 h-12 bg-orange-50 rounded-lg flex items-center justify-center text-2xl">
                🏷️
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
        <div className="flex items-center gap-3">
          {/* Search */}
          <div className="flex-1 relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">🔍</span>
            <input
              type="text"
              placeholder="Buscar por nome, telefone ou email..."
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          {/* Filter Button */}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors ${
              hasActiveFilters
                ? 'bg-primary-50 border-primary-300 text-primary-700'
                : 'bg-white border-slate-300 text-slate-700 hover:bg-slate-50'
            }`}
          >
            🔽 Filtros
            {hasActiveFilters && (
              <span className="ml-1 px-2 py-0.5 bg-primary-600 text-white text-xs rounded-full">
                {Object.values(filters).filter(v => v !== '').length}
              </span>
            )}
          </button>

          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-2 px-4 py-2 text-sm text-slate-600 hover:text-slate-900 transition-colors"
            >
              ❌ Limpar
            </button>
          )}
        </div>

        {/* Advanced Filters */}
        {showFilters && (
          <div className="mt-4 pt-4 border-t border-slate-200 grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Status</label>
              <select
                value={filters.status}
                onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="">Todos</option>
                <option value="agendamento_pendente">⚠️ Pendente de Confirmação</option>
                <option value="novo">Novo</option>
                <option value="qualificado">Qualificado</option>
                <option value="agendado">Agendado</option>
                <option value="sem_imovel_disponivel">Sem Imóvel Disponível</option>
                <option value="iniciado">Iniciado</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Finalidade</label>
              <select
                value={filters.finalidade}
                onChange={(e) => setFilters({ ...filters, finalidade: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="">Todas</option>
                <option value="sale">Compra</option>
                <option value="rent">Locação</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Tipo de Imóvel</label>
              <select
                value={filters.tipo}
                onChange={(e) => setFilters({ ...filters, tipo: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="">Todos</option>
                <option value="house">Casa</option>
                <option value="apartment">Apartamento</option>
                <option value="commercial">Comercial</option>
                <option value="land">Terreno</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Cidade</label>
              <input
                type="text"
                placeholder="Ex: Mogi das Cruzes"
                value={filters.cidade}
                onChange={(e) => setFilters({ ...filters, cidade: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Valor Mínimo (R$)</label>
              <input
                type="number"
                placeholder="Ex: 200000"
                value={filters.valorMin}
                onChange={(e) => setFilters({ ...filters, valorMin: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Valor Máximo (R$)</label>
              <input
                type="number"
                placeholder="Ex: 500000"
                value={filters.valorMax}
                onChange={(e) => setFilters({ ...filters, valorMax: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Código do Imóvel</label>
              <input
                type="text"
                placeholder="Ex: A738"
                value={filters.codigoImovel}
                onChange={(e) => setFilters({ ...filters, codigoImovel: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Data Inicial</label>
              <input
                type="date"
                value={filters.dateFrom}
                onChange={(e) => setFilters({ ...filters, dateFrom: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Data Final</label>
              <input
                type="date"
                value={filters.dateTo}
                onChange={(e) => setFilters({ ...filters, dateTo: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>
        )}
      </div>

      {/* Results Count */}
      {!loading && !error && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-600">
            Mostrando <span className="font-semibold text-slate-900">{filteredData?.length || 0}</span> de{' '}
            <span className="font-semibold text-slate-900">{data?.length || 0}</span> leads
          </p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
          <div className="inline-block w-8 h-8 border-4 border-primary-600 border-t-transparent rounded-full animate-spin"></div>
          <p className="mt-4 text-sm text-slate-600">Carregando leads...</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-800">
          <p className="font-medium">Erro ao carregar leads</p>
          <p className="text-sm mt-1">{error}</p>
        </div>
      )}

      {/* Table */}
      {!loading && !error && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">ID</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">Nome</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">Telefone</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">Email</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">Preferências</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">Última Conversa</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">Ações</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {sortedData.map((lead) => (
                  <tr key={lead.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">#{lead.id}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-slate-900">{lead.name || <span className="text-slate-400 italic">Não informado</span>}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-sm text-slate-600">{formatPhone(lead.phone)}</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-sm text-slate-600">{lead.email || <span className="text-slate-400 italic">-</span>}</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">{getStatusBadge(lead.status)}</td>
                    <td className="px-6 py-4">
                      {(() => {
                        const hasData = lead.finalidade || lead.tipo || lead.cidade || lead.preco_min || lead.preco_max
                        return hasData ? (
                          <div className="flex flex-wrap gap-2 max-w-xs">
                            {lead.finalidade && (
                              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                                {lead.finalidade === 'sale' ? '🏠 Compra' : '🔑 Locação'}
                              </span>
                            )}
                            {lead.tipo && (
                              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                {lead.tipo === 'apartment' ? '🏢 Apto' : lead.tipo === 'house' ? '🏡 Casa' : lead.tipo}
                              </span>
                            )}
                            {lead.cidade && (
                              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                                📍 {lead.cidade}
                              </span>
                            )}
                            {(lead.preco_min || lead.preco_max) && (
                              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                💰 {formatPrice(lead.preco_min)} - {formatPrice(lead.preco_max)}
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-slate-400 text-sm">-</span>
                        )
                      })()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600">
                      {formatDate(lead.last_inbound_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      {lead.status === 'agendamento_pendente' && (
                        <button
                          onClick={() => handleConfirmVisit(lead.id)}
                          disabled={confirmingVisitId === lead.id}
                          className="px-3 py-1 bg-red-600 text-white rounded text-xs hover:bg-red-700 disabled:opacity-50 transition-colors"
                        >
                          {confirmingVisitId === lead.id ? '⏳' : '✓ Confirmar'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Config Modal */}
      {showConfigModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4 shadow-lg">
            <h2 className="text-xl font-bold text-slate-900 mb-4">Configuração de Notificações</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Destinatários WhatsApp</label>
                <textarea
                  value={recipients.join('\n')}
                  onChange={(e) => setRecipients(e.target.value.split('\n').filter(r => r.trim()))}
                  placeholder="Um número por linha (ex: 5511999990000)"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm"
                  rows={4}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Template WhatsApp (opcional)</label>
                <input
                  type="text"
                  value={template}
                  onChange={(e) => setTemplate(e.target.value)}
                  placeholder="Ex: visit_confirmed_internal"
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm"
                />
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowConfigModal(false)}
                className="flex-1 px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={() => handleSaveConfig()}
                className="flex-1 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
              >
                Salvar
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )

  async function handleConfirmVisit(leadId: number) {
    const visit = visits.find(v => v.lead_id === leadId)
    if (!visit) {
      alert('Nenhuma visita pendente encontrada para este lead')
      return
    }

    setConfirmingVisitId(visit.id)
    try {
      const token = localStorage.getItem('auth_token')
      const res = await fetch(`/api/admin/re/visits/${visit.id}/confirm`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })
      if (res.ok) {
        alert('Visita confirmada com sucesso!')
        loadLeads()
      } else {
        alert('Erro ao confirmar visita')
      }
    } catch (e: unknown) {
      alert('Erro: ' + (e instanceof Error ? e.message : 'erro'))
    } finally {
      setConfirmingVisitId(null)
    }
  }

  async function handleSaveConfig() {
    try {
      const token = localStorage.getItem('auth_token')
      
      // Salvar recipients
      await fetch('/api/admin/re/booking/recipients', {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ recipients })
      })

      // Salvar template
      if (template) {
        await fetch('/api/admin/re/booking/template', {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ template_name: template })
        })
      }

      alert('Configuração salva com sucesso!')
      setShowConfigModal(false)
    } catch (e: unknown) {
      alert('Erro ao salvar: ' + (e instanceof Error ? e.message : 'erro'))
    }
  }
}
