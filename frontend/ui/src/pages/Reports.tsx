import React, { useEffect, useMemo, useState } from 'react'
import ReactECharts from 'echarts-for-react'
import { apiFetch } from '../lib/auth'

type MetricsResponse = {
  generated_at: string
  labels: string[]
  leads_por_mes: number[]
  conversas_whatsapp: number[]
  taxa_conversao: number[]
  kpis: {
    total_leads_periodo: number
    novos_leads_hoje: number
    taxa_conversao_geral: number
  }
  lead_funnel: { [key: string]: number };
  lead_sources: { [key: string]: number };
}

export default function Reports() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null)
  const [periodMonths, setPeriodMonths] = useState<number>(6)
  const [channel, setChannel] = useState<string>('whatsapp')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')

  useEffect(() => {
    let alive = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const qp = new URLSearchParams()
        if (startDate && endDate) {
          qp.set('start_date', startDate)
          qp.set('end_date', endDate)
        } else {
          qp.set('period_months', String(periodMonths))
        }
        if (channel) qp.set('channel', channel)
        const res = await apiFetch(`/api/metrics/overview?${qp.toString()}`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const js = await res.json()
        if (alive) setMetrics(js)
      } catch (e) {
        const err = e as Error;
        if (alive) setError(err?.message || 'Falha ao carregar métricas');
      } finally {
        if (alive) setLoading(false)
      }
    }
    load()
    return () => { alive = false }
  }, [periodMonths, channel, startDate, endDate])

  const meses = useMemo(() => metrics?.labels || ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun'], [metrics?.labels])

  const leadsOption = useMemo(() => ({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: meses },
    yAxis: { type: 'value' },
    series: [{
      name: 'Leads', type: 'bar', data: metrics?.leads_por_mes ?? [12, 18, 25, 22, 30, 28],
      itemStyle: { color: '#2563eb' }
    }]
  }), [metrics, meses])

  const whatsOption = useMemo(() => ({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: meses },
    yAxis: { type: 'value' },
    series: [{ name: 'Conversas WhatsApp', type: 'line', data: metrics?.conversas_whatsapp ?? [80, 110, 95, 120, 130, 140], smooth: true, lineStyle: { width: 3, color: '#16a34a' } }]
  }), [metrics, meses])

  const convOption = useMemo(() => ({
    tooltip: { trigger: 'axis', formatter: (params: { axisValue: string; data: number }[]) => {
      if (params && params.length > 0 && params[0]) {
        return `${params[0].axisValue}: ${params[0].data}%`;
      }
      return '';
    } },
    xAxis: { type: 'category', data: meses },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    series: [{ name: 'Conversão', type: 'line', data: metrics?.taxa_conversao ?? [8, 9, 11, 10, 12, 13], areaStyle: {}, itemStyle: { color: '#9333ea' } }]
  }), [metrics, meses])

  const funilOption = useMemo(() => {
    const funnelData = metrics?.lead_funnel || {};
    const statusOrder = ['iniciado', 'novo', 'qualificado', 'agendamento_pendente', 'agendado', 'sem_imovel_disponivel'];
    const labels = statusOrder.map(s => s.replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase()));
    const data = statusOrder.map(s => funnelData[s] || 0);

    return {
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'category',
        data: labels,
        axisLabel: {
          interval: 0,
          rotate: 30
        }
      },
      yAxis: { type: 'value' },
      series: [{
        name: 'Leads',
        type: 'bar',
        data: data,
        itemStyle: { color: '#f97316' }
      }]
    };
  }, [metrics]);

  const sourcesOption = useMemo(() => {
    const sourcesData = metrics?.lead_sources || {};
    const data = Object.entries(sourcesData).map(([name, value]) => ({ name, value }));

    return {
      tooltip: { trigger: 'item' },
      legend: { top: '5%', left: 'center' },
      series: [{
        name: 'Origem',
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: { show: false, position: 'center' },
        emphasis: {
          label: { show: true, fontSize: '20', fontWeight: 'bold' }
        },
        labelLine: { show: false },
        data: data
      }]
    };
  }, [metrics]);

  return (
    <section className="space-y-5">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">Relatórios</h1>
        <div className="text-sm text-slate-500">Indicadores operacionais e de marketing</div>
      </header>

      {!loading && !error && metrics?.kpis && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="card p-4">
            <div className="text-sm text-slate-600">Total de Leads no Período</div>
            <div className="text-3xl font-bold text-slate-800 mt-1">{metrics.kpis.total_leads_periodo}</div>
          </div>
          <div className="card p-4">
            <div className="text-sm text-slate-600">Novos Leads Hoje</div>
            <div className="text-3xl font-bold text-slate-800 mt-1">{metrics.kpis.novos_leads_hoje}</div>
          </div>
          <div className="card p-4">
            <div className="text-sm text-slate-600">Taxa de Conversão Geral</div>
            <div className="text-3xl font-bold text-slate-800 mt-1">{metrics.kpis.taxa_conversao_geral}%</div>
          </div>
        </div>
      )}

      <div className="card grid grid-cols-1 md:grid-cols-4 gap-3">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Período</label>
          <select
            className="select"
            value={periodMonths}
            onChange={e => setPeriodMonths(Number(e.target.value))}
          >
            <option value={6}>Últimos 6 meses</option>
            <option value={12}>Últimos 12 meses</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Canal</label>
          <select
            className="select"
            value={channel}
            onChange={e => setChannel(e.target.value)}
          >
            <option value="whatsapp">WhatsApp</option>
            <option value="all">Todos</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Data inicial</label>
          <input
            type="date"
            className="input"
            value={startDate}
            onChange={e => setStartDate(e.target.value)}
            max={endDate || undefined}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Data final</label>
          <input
            type="date"
            className="input"
            value={endDate}
            onChange={e => setEndDate(e.target.value)}
            min={startDate || undefined}
          />
        </div>
        <div className="md:col-span-4 flex items-center gap-2 pt-1">
          <button
            onClick={() => { setStartDate(''); setEndDate(''); }}
            disabled={loading || (!startDate && !endDate)}
            className="btn btn-ghost disabled:opacity-50"
          >
            Limpar datas
          </button>
          <div className="text-xs text-slate-500">
            {startDate && endDate ? `Período: ${startDate} a ${endDate}` : `Período rápido: ${periodMonths} meses`}
          </div>
        </div>
      </div>

      {loading && <div className="text-sm text-slate-500">Carregando dados...</div>}
      {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">{error}</div>}

      {!loading && !error && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div className="card p-4">
            <div className="card-header">Leads por mês</div>
            <ReactECharts option={leadsOption} style={{ height: 280 }} notMerge={true} lazyUpdate={true} />
          </div>

          <div className="card p-4">
            <div className="card-header">Conversas WhatsApp</div>
            <ReactECharts option={whatsOption} style={{ height: 280 }} notMerge={true} lazyUpdate={true} />
          </div>

          <div className="card p-4">
            <div className="card-header">Taxa de conversão (%)</div>
            <ReactECharts option={convOption} style={{ height: 320 }} notMerge={true} lazyUpdate={true} />
          </div>

          <div className="card p-4">
            <div className="card-header">Funil de Leads (Status Atual)</div>
            <ReactECharts option={funilOption} style={{ height: 320 }} notMerge={true} lazyUpdate={true} />
          </div>

          <div className="card p-4 lg:col-span-2">
            <div className="card-header">Origem dos Leads (Período)</div>
            <ReactECharts option={sourcesOption} style={{ height: 320 }} notMerge={true} lazyUpdate={true} />
          </div>
        </div>
      )}
    </section>
  )
}
