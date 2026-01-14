import React, { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../lib/auth'
import { useTenant } from '../contexts/TenantContext'
import { DndContext, closestCorners, DragEndEvent, useSensor, PointerSensor, useSensors } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy, useSortable, arrayMove } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

const STATUS_COLUMN_ORDER = ['iniciado', 'novo', 'qualificado', 'agendamento_pendente', 'agendado', 'sem_imovel_disponivel'] as const;

type LeadsConfig = {
  domain: string
  has_published_flow: boolean
  lead_summary_fields: Array<Record<string, unknown>>
  lead_kanban: { stages?: Array<{ id?: string | null; label?: string | null }> } | null
}

type ColumnProps = {
  id: string;
  title: string;
  leads: Lead[];
  filters: Filters;
  getStatusBadge: (status?: string | null) => React.ReactNode;
  formatPhone: (phone?: string | null) => string;
  formatDate: (date?: string | null) => string;
  onCardClick: (lead: Lead) => void;
}

function LeadSummaryDisplay({ summary }: { summary: Array<{ key?: string | null; label?: string | null; value?: unknown }> | null | undefined }) {
  if (!summary || summary.length === 0) return null;

  const visible = summary.filter((f) => {
    const v = (f?.value ?? null) as unknown;
    if (v === null || v === undefined) return false;
    if (typeof v === 'string' && !v.trim()) return false;
    return true;
  });

  if (visible.length === 0) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3 text-sm">
      {visible.map((f, idx) => (
        <div key={(f.key as string) || `${idx}`}>
          <strong className="text-slate-600">{f.label || f.key}:</strong>
          <span className="text-slate-800 ml-2">{String(f.value)}</span>
        </div>
      ))}
    </div>
  );
}

function GenericPreferencesDisplay({ preferences }: { preferences: Record<string, unknown> | null | undefined }) {
  if (!preferences) {
    return <p className="text-sm text-slate-600">Nenhuma preferência registrada.</p>;
  }

  const entries = Object.entries(preferences).filter(([, v]) => {
    if (v === null || v === undefined) return false;
    if (typeof v === 'string' && !v.trim()) return false;
    if (Array.isArray(v) && v.length === 0) return false;
    return true;
  });

  if (entries.length === 0) {
    return <p className="text-sm text-slate-600">Nenhuma preferência registrada.</p>;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3 text-sm">
      {entries.slice(0, 12).map(([k, v]) => (
        <div key={k}>
          <strong className="text-slate-600">{k}:</strong>
          <span className="text-slate-800 ml-2">{String(v)}</span>
        </div>
      ))}
    </div>
  );
}

function Column({ title, leads, filters, getStatusBadge, formatPhone, formatDate, onCardClick }: ColumnProps) {
  const filteredLeads = leads.filter((lead: Lead) => {
    if (filters.search) {
      const search = filters.search.toLowerCase();
      return (
        lead.name?.toLowerCase().includes(search) ||
        lead.phone?.toLowerCase().includes(search) ||
        lead.email?.toLowerCase().includes(search)
      );
    }
    return true;
  });

  return (
    <div className="w-80 bg-slate-100 rounded-lg p-2 flex-shrink-0">
      <h3 className="font-semibold text-slate-700 px-2 py-1 mb-2">{title} <span className="text-sm text-slate-500 font-normal">({filteredLeads.length})</span></h3>
      <SortableContext items={filteredLeads.map(l => l.id)} strategy={verticalListSortingStrategy}>
        <div className="space-y-2 h-[600px] overflow-y-auto">
          {filteredLeads.map((lead: Lead) => (
            <LeadCard key={lead.id} lead={lead} getStatusBadge={getStatusBadge} formatPhone={formatPhone} formatDate={formatDate} onCardClick={onCardClick} />
          ))}
        </div>
      </SortableContext>
    </div>
  );
}

type LeadCardProps = {
  lead: Lead;
  getStatusBadge: (status?: string | null) => React.ReactNode;
  formatPhone: (phone?: string | null) => string;
  formatDate: (date?: string | null) => string;
  onCardClick: (lead: Lead) => void;
}

function PreferencesDisplay({ preferences }: { preferences: Record<string, unknown> | null | undefined }) {
  if (!preferences) {
    return <p className="text-sm text-slate-600">Nenhuma preferência registrada.</p>;
  }

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
  };

  const preferenceLabels: Record<string, string> = {
    purpose: 'Finalidade',
    type: 'Tipo de Imóvel',
    city: 'Cidade',
    neighborhood: 'Bairro',
    bedrooms: 'Quartos',
    price_min: 'Valor Mínimo',
    price_max: 'Valor Máximo',
  };

  const purposeValues: Record<string, string> = {
    sale: 'Venda',
    rent: 'Aluguel',
  };

  const typeValues: Record<string, string> = {
    house: 'Casa',
    apartment: 'Apartamento',
    commercial: 'Comercial',
    land: 'Terreno',
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3 text-sm">
      {Object.entries(preferenceLabels).map(([key, label]) => {
        let value = preferences[key];
        if (value === null || value === undefined || value === '') return null;

        if (key === 'purpose') {
          const k = String(value)
          value = purposeValues[k] || value
        }
        if (key === 'type') {
          const k = String(value)
          value = typeValues[k] || value
        }
        if (key === 'price_min' || key === 'price_max') value = typeof value === 'number' ? formatCurrency(value) : value;

        return (
          <div key={key}>
            <strong className="text-slate-600">{label}:</strong>
            <span className="text-slate-800 ml-2 capitalize">{String(value)}</span>
          </div>
        );
      })}
    </div>
  );
}

function LeadCard({ lead, getStatusBadge, formatPhone, formatDate, onCardClick }: LeadCardProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: lead.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 1 : 0,
  };

  return (
    <div 
      ref={setNodeRef} 
      style={style} 
      {...attributes} 
      {...listeners} 
      onClick={() => onCardClick(lead)}
      className={`bg-white rounded-md shadow-sm p-3 border cursor-pointer hover:border-primary-300 transition-colors ${isDragging ? 'border-primary-500' : 'border-white'}`}>
      <div className="font-semibold text-slate-800">{lead.name || 'Sem nome'}</div>
      <div className="text-sm text-slate-600">{formatPhone(lead.phone)}</div>
      <div className="text-xs text-slate-500 mt-1">{formatDate(lead.last_inbound_at)}</div>

      {lead.lead_summary && lead.lead_summary.filter(item => item.value).length > 0 && (
        <div className="mt-2 pt-2 border-t border-slate-200 space-y-1">
          {lead.lead_summary.slice(0, 3).map((item, index) => (
            item.value ? (
              <div key={(item.key as string) || index} className="text-xs text-slate-600 flex items-center justify-between gap-2">
                <span className="font-medium truncate">{item.label}:</span>
                <span className="text-slate-800 font-semibold truncate max-w-[120px]">{String(item.value)}</span>
              </div>
            ) : null
          ))}
        </div>
      )}

      <div className="mt-2">{getStatusBadge(lead.status)}</div>
    </div>
  );
}

interface Lead {
  id: number
  name?: string | null
  phone?: string | null
  email?: string | null
  source?: string | null
  status?: string | null
  preferences?: Record<string, unknown> | null
  lead_summary?: Array<{ key?: string | null; label?: string | null; value?: unknown }> | null
  lead_kanban?: { stages?: Array<{ id?: string | null; label?: string | null }> } | null
  // Aliases retornados pelo backend (pt-BR)
  nome?: string | null
  telefone?: string | null
  origem?: string | null
  preferencias?: Record<string, unknown> | null
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
  const { tenantId } = useTenant()
  const [data, setData] = useState<Lead[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [leadsConfig, setLeadsConfig] = useState<LeadsConfig | null>(null)
  const [loadingConfig, setLoadingConfig] = useState(false)
  const [showFilters, setShowFilters] = useState(false)
  const [groupBy, setGroupBy] = useState<'status' | 'stage'>('status')
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

  const [showConfigModal, setShowConfigModal] = useState(false)
  const [recipients, setRecipients] = useState<string[]>([])
  const [template, setTemplate] = useState<string>('')

  // Kanban state
  const [columns, setColumns] = useState<Record<string, Lead[]>>({})
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
  const [stageConfig, setStageConfig] = useState<Record<string, string>>({})
  const [stageOrder, setStageOrder] = useState<string[]>([])

  const activeDomain = (leadsConfig?.domain || 'real_estate').trim() || 'real_estate'
  const hasPublishedFlow = !!leadsConfig?.has_published_flow
  const isRealEstate = activeDomain === 'real_estate'

  const statusOrder = useMemo(() => {
    if (isRealEstate) return [...STATUS_COLUMN_ORDER] as unknown as string[]
    return ['iniciado', 'novo', 'qualificado', 'agendamento_pendente', 'agendado']
  }, [isRealEstate])

  function getLeadStage(lead: Lead): string {
    const prefs = lead.preferences || null;
    const stage = (prefs && typeof prefs === 'object' ? (prefs as Record<string, unknown>)['stage'] : null) as unknown;
    const s = (stage ?? '').toString().trim();
    return s || 'start';
  }

  function groupLeads(leads: Lead[], mode: 'status' | 'stage'): Record<string, Lead[]> {
    if (mode === 'stage') {
      return leads.reduce((acc, lead) => {
        const stage = getLeadStage(lead);
        if (!acc[stage]) acc[stage] = [];
        acc[stage]!.push(lead);
        return acc;
      }, {} as Record<string, Lead[]>);
    }

    // status
    const grouped = leads.reduce((acc, lead) => {
      const status = lead.status || 'iniciado';
      if (!acc[status]) acc[status] = [];
      acc[status]!.push(lead);
      return acc;
    }, {} as Record<string, Lead[]>);

    // garante colunas conhecidas mesmo vazias (para order fixo)
    for (const s of statusOrder) {
      if (!grouped[s]) grouped[s] = [];
    }
    return grouped;
  }

  const columnOrder = useMemo(() => {
    if (groupBy === 'status') return [...statusOrder];
    const keys = Object.keys(columns || {});
    const present = new Set(keys.map((k) => (k || '').trim()).filter(Boolean));
    const ordered = (stageOrder || []).filter((k) => present.has(k));
    const remaining = Array.from(present).filter((k) => !ordered.includes(k));
    remaining.sort((a, b) => {
      if (a === 'start') return -1;
      if (b === 'start') return 1;
      return a.localeCompare(b);
    });
    const out = [...ordered, ...remaining];
    return out.length ? out : ['start'];
  }, [columns, groupBy, stageOrder, statusOrder]);

  function getColumnTitle(columnId: string): string {
    if (groupBy === 'status') {
      return columnId.replace(/_/g, ' ').replace(/^\w/, (c: string) => c.toUpperCase());
    }
    const label = stageConfig[columnId];
    if (label) return label;
    return columnId.replace(/_/g, ' ').replace(/^\w/, (c: string) => c.toUpperCase());
  }

  useEffect(() => {
    loadLeadsConfig();
    loadLeads(filters);
    loadConfig();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantId]);

  async function loadLeadsConfig() {
    setLoadingConfig(true)
    try {
      const res = await apiFetch('/api/re/leads/config', { cache: 'no-store' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const js = (await res.json()) as LeadsConfig
      setLeadsConfig(js)

      const nextStageConfig: Record<string, string> = {}
      const nextStageOrder: string[] = []
      const stages = js?.lead_kanban?.stages
      if (Array.isArray(stages)) {
        for (const s of stages) {
          const id = (s?.id ?? '').toString().trim()
          const label = (s?.label ?? '').toString().trim()
          if (!id || !label) continue
          nextStageConfig[id] = label
          nextStageOrder.push(id)
        }
      }
      setStageConfig(nextStageConfig)
      setStageOrder(nextStageOrder)

      setGroupBy((prev) => {
        if (prev === 'stage' && (!js?.has_published_flow || !nextStageOrder.length)) return 'status'
        return prev
      })
    } catch {
      setLeadsConfig(null)
      setStageConfig({})
      setStageOrder([])
      setGroupBy('status')
    } finally {
      setLoadingConfig(false)
    }
  }

  // Gatilho para recarregar os leads quando os filtros mudam
  useEffect(() => {
    const handler = setTimeout(() => {
      loadLeads(filters);
    }, 500); // Debounce para evitar chamadas excessivas

    return () => {
      clearTimeout(handler);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  async function loadLeads(currentFilters: Filters) {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams();
      params.append('limit', '500');

      // Adiciona filtros à query string apenas se tiverem valor
      if (currentFilters.status) params.append('status', currentFilters.status);
      if (currentFilters.finalidade) params.append('finalidade', currentFilters.finalidade);
      if (currentFilters.tipo) params.append('tipo', currentFilters.tipo);
      if (currentFilters.cidade) params.append('cidade', currentFilters.cidade);
      if (currentFilters.valorMin) params.append('preco_min', currentFilters.valorMin);
      if (currentFilters.valorMax) params.append('preco_max', currentFilters.valorMax);
      if (currentFilters.codigoImovel) params.append('external_property_id', currentFilters.codigoImovel);
      // NOTE: date filters are not implemented in backend yet

      const res = await apiFetch(`/api/re/leads?${params.toString()}`, { cache: 'no-store' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const js: unknown = await res.json()
      const raw = Array.isArray(js) ? (js as unknown[]) : []

      const normalizePreferences = (prefs: Record<string, unknown> | null | undefined) => {
        if (!prefs) return prefs
        // A UI espera: purpose/type/city/neighborhood/bedrooms/price_min/price_max
        // Mas podemos receber: finalidade/tipo/cidade/bairro/dormitorios/preco_min/preco_max
        const p = prefs as Record<string, unknown>
        return {
          ...p,
          purpose: p.purpose ?? p.finalidade,
          type: p.type ?? p.tipo,
          city: p.city ?? p.cidade,
          neighborhood: p.neighborhood ?? p.bairro,
          bedrooms: p.bedrooms ?? p.dormitorios,
          price_min: p.price_min ?? p.preco_min,
          price_max: p.price_max ?? p.preco_max,
        }
      }

      const leads: Lead[] = raw.map((row: unknown) => {
        const r = (row ?? {}) as Record<string, unknown>
        const prefs = normalizePreferences((r?.preferences ?? r?.preferencias) as Record<string, unknown> | null | undefined)
        return {
          ...(r as unknown as Lead),
          name: (r?.name ?? r?.nome) as string | null | undefined,
          phone: (r?.phone ?? r?.telefone) as string | null | undefined,
          source: (r?.source ?? r?.origem) as string | null | undefined,
          preferences: prefs ?? null,
          lead_summary: (r?.lead_summary as Lead['lead_summary']) ?? null,
          lead_kanban: (r?.lead_kanban as Lead['lead_kanban']) ?? null,
        } as Lead
      })

      setData(leads)

      setColumns(groupLeads(leads, groupBy))
      
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

    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'erro')
    } finally {
      setLoading(false)
    }
  }

  async function loadConfig() {
    try {
      const recRes = await apiFetch('/api/admin/re/booking/recipients', { cache: 'no-store' })
      if (recRes.ok) {
        const rec = await recRes.json()
        if (rec?.recipients) setRecipients(rec.recipients)
      }
      const tplRes = await apiFetch('/api/admin/re/booking/template', { cache: 'no-store' })
      if (tplRes.ok) {
        const tpl = await tplRes.json()
        if (typeof tpl?.template_name === 'string') setTemplate(tpl.template_name)
      }
    } catch {
      // silencioso
    }
  }

  // filteredData is not used in Kanban view, but kept for potential future toggle
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

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over) return;

    const activeId = active.id;
    const overId = over.id;

    const activeContainer = active.data.current?.sortable.containerId;
    const overContainer = over.data.current?.sortable.containerId || over.id;

    if (activeContainer !== overContainer) {
      if (groupBy === 'stage') {
        // Em agrupamento por etapa, não alteramos status via drag&drop.
        // Mantém comportamento de visualização operacional.
        return;
      }
      // Move between columns
      const sourceColumn = columns[activeContainer];
      const destColumn = columns[overContainer];
      if (!sourceColumn || !destColumn) return;

      const activeIndex = sourceColumn.findIndex(l => l.id === activeId);
      const overIndex = destColumn.findIndex(l => l.id === overId);

      const [movedItem] = sourceColumn.splice(activeIndex, 1);
      if (!movedItem) return;

      destColumn.splice(overIndex, 0, movedItem);

      setColumns(prev => ({
        ...prev,
        [activeContainer]: [...sourceColumn],
        [overContainer]: [...destColumn],
      }));

      // API call
      try {
        await apiFetch(`/api/re/leads/${activeId}/status`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: overContainer }),
        });
      } catch (err) {
        console.error("Failed to update lead status:", err);
        // Revert on error
        sourceColumn.splice(activeIndex, 0, movedItem);
        destColumn.splice(overIndex, 1);
        setColumns(prev => ({ ...prev, [activeContainer]: [...sourceColumn], [overContainer]: [...destColumn] }));
        alert('Falha ao atualizar o status do lead.');
      }
    } else {
      // Move within the same column
      const column = columns[activeContainer];
      if (!column) return;

      const oldIndex = column.findIndex(l => l.id === activeId);
      const newIndex = column.findIndex(l => l.id === overId);

      if (oldIndex !== newIndex) {
        setColumns(prev => ({
          ...prev,
          [activeContainer]: arrayMove(column, oldIndex, newIndex),
        }));
      }
    }
  };

  return (
    <section className="space-y-6">
      {/* Header */}
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Gestão de Leads</h1>
          <p className="text-sm text-slate-600 mt-1">Gerencie e acompanhe todos os seus leads</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 bg-white border border-slate-300 rounded-lg px-3 py-2">
            <span className="text-sm text-slate-600">Agrupar por</span>
            <select
              value={groupBy}
              onChange={(e) => {
                const v = e.target.value === 'stage' ? 'stage' : 'status';
                setGroupBy(v);
                setColumns(groupLeads(data || [], v));
              }}
              className="text-sm bg-transparent outline-none"
            >
              <option value="status">Status</option>
              <option value="stage" disabled={!hasPublishedFlow || stageOrder.length === 0}>Etapa (Flow)</option>
            </select>
          </div>
          <button
            onClick={() => setShowConfigModal(true)}
            className="px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors text-sm font-medium"
          >
            ⚙️ Configurar notificações
          </button>
          <button
            onClick={() => loadLeads(filters)}
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
                <p className="text-sm font-medium text-orange-600">{isRealEstate ? 'Sem Imóvel' : 'Sem Match'}</p>
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

            {isRealEstate && (
              <>
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
              </>
            )}

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

      {/* Kanban Board */}
      {!loading && !error && !loadingConfig && !hasPublishedFlow && (
        <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
          <p className="text-sm text-slate-700 font-medium">Este tenant ainda não tem um Flow publicado.</p>
          <p className="mt-1 text-sm text-slate-600">Assim que você publicar um Flow com etapas (Kanban), a visão por etapa fica disponível aqui.</p>
          <div className="mt-4 flex items-center justify-center gap-3">
            <a href="/flows" className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors text-sm font-medium">Ir para Flows</a>
            <button
              type="button"
              onClick={() => loadLeadsConfig()}
              className="px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors text-sm font-medium"
            >
              Recarregar config
            </button>
          </div>
        </div>
      )}

      {!loading && !error && (loadingConfig || hasPublishedFlow) && (
        <DndContext sensors={sensors} collisionDetection={closestCorners} onDragEnd={handleDragEnd}>
          <div className="flex gap-4 overflow-x-auto pb-4">
            {columnOrder.map((columnId: string) => (
              <Column key={columnId} id={columnId} title={getColumnTitle(columnId)} leads={columns[columnId] || []} filters={filters} getStatusBadge={getStatusBadge} formatPhone={formatPhone} formatDate={formatDate} onCardClick={setSelectedLead} />
            ))}
          </div>
        </DndContext>
      )}


      {/* Lead Details Modal */}
      {selectedLead && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setSelectedLead(null)}>
          <div className="bg-white rounded-xl p-6 max-w-2xl w-full mx-4 shadow-lg max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-xl font-bold text-slate-900 mb-1">{selectedLead.name || 'Lead Sem Nome'}</h2>
                <p className="text-sm text-slate-600">{formatPhone(selectedLead.phone)}</p>
              </div>
              <button 
                onClick={() => setSelectedLead(null)}
                className="text-slate-500 hover:text-slate-800 transition-colors"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
              </button>
            </div>

            <div className="mt-4 pt-4 border-t border-slate-200 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div><strong className="text-slate-600">Status:</strong> {getStatusBadge(selectedLead.status)}</div>
              <div><strong className="text-slate-600">Origem:</strong> <span className="capitalize">{selectedLead.source || '-'}</span></div>
              <div><strong className="text-slate-600">Último Contato:</strong> {formatDate(selectedLead.last_inbound_at)}</div>
              <div><strong className="text-slate-600">{isRealEstate ? 'ID do Imóvel' : 'ID Externo'}:</strong> {selectedLead.external_property_id || '-'}</div>
            </div>

            <div className="mt-4 pt-4 border-t border-slate-200">
              <h3 className="text-lg font-semibold text-slate-800 mb-2">Resumo do Lead</h3>
              <div className="bg-slate-50 p-4 rounded-lg mt-2">
                {selectedLead.lead_summary && selectedLead.lead_summary.length > 0 ? (
                  <LeadSummaryDisplay summary={selectedLead.lead_summary} />
                ) : (
                  (isRealEstate ? <PreferencesDisplay preferences={selectedLead.preferences} /> : <GenericPreferencesDisplay preferences={selectedLead.preferences} />)
                )}
              </div>
            </div>

            <div className="flex justify-end mt-6">
              <button
                onClick={() => setSelectedLead(null)}
                className="px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors"
              >
                Fechar
              </button>
            </div>
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


  async function handleSaveConfig() {
    try {
      // Salvar recipients
      await apiFetch('/api/admin/re/booking/recipients', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recipients })
      })

      // Salvar template
      if (template) {
        await apiFetch('/api/admin/re/booking/template', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
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
