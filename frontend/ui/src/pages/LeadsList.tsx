import React, { useEffect, useState } from 'react'

interface Lead {
  id: number
  name?: string | null
  phone?: string | null
  email?: string | null
  source?: string | null
  status?: string | null
  preferences?: Record<string, any> | null
  property_interest_id?: number | null
  external_property_id?: string | null
  last_inbound_at?: string | null
  created_at?: string | null
}

interface Filters {
  search: string
  status: string
  source: string
  dateFrom: string
  dateTo: string
  propertyId: string
  externalPropertyId: string
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
    source: '',
    dateFrom: '',
    dateTo: '',
    propertyId: '',
    externalPropertyId: '',
    finalidade: '',
    tipo: '',
    cidade: '',
    valorMin: '',
    valorMax: ''
  })

  const [stats, setStats] = useState({
    total: 0,
    novos: 0,
    qualificados: 0,
    hoje: 0
  })

  useEffect(() => {
    loadLeads()
  }, [])

  async function loadLeads() {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/re/leads?limit=200', { cache: 'no-store' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const leads = await res.json()
      setData(leads)
      
      // Calcular estatísticas
      const hoje = new Date().toISOString().split('T')[0] || ''
      setStats({
        total: leads.length,
        novos: leads.filter((l: Lead) => l.status === 'novo').length,
        qualificados: leads.filter((l: Lead) => l.status === 'qualificado').length,
        hoje: leads.filter((l: Lead) => l.last_inbound_at?.startsWith(hoje) ?? false).length
      })
    } catch (e: any) {
      setError(e?.message || 'erro')
    } finally {
      setLoading(false)
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

    // Filtro de origem
    if (filters.source && lead.source !== filters.source) return false

    // Filtro de ID do imóvel
    if (filters.propertyId && lead.property_interest_id?.toString() !== filters.propertyId) return false

    // Filtro de código externo
    if (filters.externalPropertyId && !lead.external_property_id?.includes(filters.externalPropertyId)) return false

    // Filtros de preferências
    if (filters.finalidade && lead.preferences?.finalidade !== filters.finalidade) return false
    if (filters.tipo && lead.preferences?.tipo !== filters.tipo) return false
    if (filters.cidade && !lead.preferences?.cidade?.toLowerCase().includes(filters.cidade.toLowerCase())) return false
    
    if (filters.valorMin && lead.preferences?.preco_max) {
      if (lead.preferences.preco_max < parseFloat(filters.valorMin)) return false
    }
    if (filters.valorMax && lead.preferences?.preco_min) {
      if (lead.preferences.preco_min > parseFloat(filters.valorMax)) return false
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

  function clearFilters() {
    setFilters({
      search: '',
      status: '',
      source: '',
      dateFrom: '',
      dateTo: '',
      propertyId: '',
      externalPropertyId: '',
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
      contatado: { label: 'Contatado', color: 'bg-yellow-100 text-yellow-800' },
      qualificado: { label: 'Qualificado', color: 'bg-green-100 text-green-800' },
      negociacao: { label: 'Negociação', color: 'bg-purple-100 text-purple-800' },
      perdido: { label: 'Perdido', color: 'bg-red-100 text-red-800' }
    }
    const s = statusMap[status || 'novo'] || { label: status || 'Novo', color: 'bg-slate-100 text-slate-800' }
    return <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${s.color}`}>{s.label}</span>
  }

  function formatDate(date?: string | null) {
    if (!date) return '-'
    const d = new Date(date)
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
  }

  function formatPrice(price?: number) {
    if (!price) return '-'
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(price)
  }

  return (
    <section className="space-y-6">
      {/* Header */}
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Gestão de Leads</h1>
          <p className="text-sm text-slate-600 mt-1">Gerencie e acompanhe todos os seus leads</p>
        </div>
        <button
          onClick={loadLeads}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors text-sm font-medium"
        >
          🔄 Atualizar
        </button>
      </header>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
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
              <p className="text-sm font-medium text-slate-600">Qualificados</p>
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
              <p className="text-sm font-medium text-slate-600">Hoje</p>
              <p className="text-3xl font-bold text-purple-600 mt-2">{stats.hoje}</p>
            </div>
            <div className="w-12 h-12 bg-purple-50 rounded-lg flex items-center justify-center text-2xl">
              📅
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
                <option value="novo">Novo</option>
                <option value="contatado">Contatado</option>
                <option value="qualificado">Qualificado</option>
                <option value="negociacao">Negociação</option>
                <option value="perdido">Perdido</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Origem</label>
              <select
                value={filters.source}
                onChange={(e) => setFilters({ ...filters, source: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="">Todas</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="site">Site</option>
                <option value="instagram">Instagram</option>
                <option value="facebook">Facebook</option>
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
              <label className="block text-sm font-medium text-slate-700 mb-1">ID do Imóvel</label>
              <input
                type="text"
                placeholder="Ex: 123"
                value={filters.propertyId}
                onChange={(e) => setFilters({ ...filters, propertyId: e.target.value })}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Código ND Imóveis</label>
              <input
                type="text"
                placeholder="Ex: A767"
                value={filters.externalPropertyId}
                onChange={(e) => setFilters({ ...filters, externalPropertyId: e.target.value })}
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
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">Origem</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">Preferências</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-slate-700 uppercase tracking-wider">Última Conversa</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-200">
                {(filteredData || []).map((lead) => (
                  <tr key={lead.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900">#{lead.id}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-slate-900">{lead.name || <span className="text-slate-400 italic">Não informado</span>}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-sm text-slate-600">{lead.phone || <span className="text-slate-400 italic">-</span>}</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-sm text-slate-600">{lead.email || <span className="text-slate-400 italic">-</span>}</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">{getStatusBadge(lead.status)}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800">
                        {lead.source || 'whatsapp'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {lead.preferences ? (
                        <div className="flex flex-wrap gap-2 max-w-xs">
                          {lead.preferences.finalidade && (
                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                              {lead.preferences.finalidade === 'sale' ? '🏠 Compra' : '🔑 Locação'}
                            </span>
                          )}
                          {lead.preferences.tipo && (
                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                              {lead.preferences.tipo === 'apartment' ? '🏢 Apto' : lead.preferences.tipo === 'house' ? '🏡 Casa' : lead.preferences.tipo}
                            </span>
                          )}
                          {lead.preferences.cidade && (
                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                              📍 {lead.preferences.cidade}
                            </span>
                          )}
                          {(lead.preferences.preco_min || lead.preferences.preco_max) && (
                            <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                              💰 {formatPrice(lead.preferences.preco_min)} - {formatPrice(lead.preferences.preco_max)}
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-slate-400 text-sm">-</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600">
                      {formatDate(lead.last_inbound_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  )
}
