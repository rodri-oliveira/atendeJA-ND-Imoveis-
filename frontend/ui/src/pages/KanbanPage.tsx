import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { listOrders, type Order, type OrderStatus, setOrderStatus } from '../lib/api'
import FiltersBar from '../components/FiltersBar'
import OrderCard from '../components/OrderCard'
import { useUIConfig } from '../config/provider'
import OrderDrawer from '../components/OrderDrawer'

export default function KanbanPage() {
  const [status, setStatus] = useState<OrderStatus | undefined>()
  const [search, setSearch] = useState<string>('')
  const [limit, setLimit] = useState<number>(50)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [orders, setOrders] = useState<Order[]>([])
  const ui = useUIConfig()
  const [selected, setSelected] = useState<string | null>(null)
  const [pauseUntilMs, setPauseUntilMs] = useState<number>(0)
  const [busyIds, setBusyIds] = useState<Set<string>>(new Set())
  const [compact, setCompact] = useState<boolean>(() => {
    try {
      const raw = localStorage.getItem('atendeja.ui.compact')
      if (raw !== null) return raw === '1'
    } catch { void 0 }
    return !!ui.ui?.compactDefault
  })
  const [colWidth] = useState<number>(() => {
    try {
      const raw = localStorage.getItem('atendeja.ui.colWidth')
      if (raw !== null) return Number(raw)
    } catch { void 0 }
    return ui.ui?.columnWidth ?? 280
  })
  const [targetCols, setTargetCols] = useState<number>(() => {
    try {
      const raw = localStorage.getItem('atendeja.ui.targetCols')
      if (raw !== null) return Number(raw)
    } catch { void 0 }
    return ui.ui?.targetColumnsDefault ?? 7
  })
  const boardRef = useRef<HTMLDivElement | null>(null)

  const COLUMNS = useMemo(() => {
    return (ui.kanban?.columns || []).map((c) => ({ key: c.status as OrderStatus, title: c.title }))
  }, [ui])

  const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e))

  const fetchData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const rows = await listOrders({ status, search: search || undefined, limit })
      setOrders(rows)
    } catch (e: unknown) {
      setError(errMsg(e) || 'Erro ao carregar pedidos')
    } finally {
      setLoading(false)
    }
  }, [status, search, limit])

  useEffect(() => {
    if (!selected) {
      fetchData()
    }
    const id = setInterval(() => {
      if (!selected && Date.now() >= pauseUntilMs) {
        fetchData()
      }
    }, 100_000) // auto-refresh a cada 100 segundos
    return () => clearInterval(id)
  }, [fetchData, pauseUntilMs, selected])

  const groups = useMemo(() => {
    const map = new Map<OrderStatus, Order[]>()
    for (const c of COLUMNS) map.set(c.key, [])
    for (const o of orders) {
      const bucket = map.get(o.status)
      if (bucket) bucket.push(o)
    }
    return map
  }, [orders, COLUMNS])

  const onChangeFilters = (next: { status?: OrderStatus; search?: string; limit?: number }) => {
    if ('status' in next) setStatus(next.status)
    if (typeof next.search !== 'undefined') setSearch(next.search || '')
    if (typeof next.limit !== 'undefined') setLimit(next.limit || 50)

    // Dispara refetch imediato usando os valores recebidos (evita esperar o próximo render)
    ;(async () => {
      try {
        setLoading(true)
        setError(null)
        const effectiveStatus = ('status' in next) ? next.status : status
        const effectiveSearch = (typeof next.search !== 'undefined') ? (next.search || '') : search
        const effectiveLimit = (typeof next.limit !== 'undefined') ? (next.limit || 50) : limit
        const rows = await listOrders({ status: effectiveStatus, search: effectiveSearch || undefined, limit: effectiveLimit })
        setOrders(rows)
      } catch (e: unknown) {
        setError(errMsg(e) || 'Erro ao carregar pedidos')
      } finally {
        setLoading(false)
      }
    })()

    // Pausa o auto-refresh por 5s após alterações de filtro para evitar corrida com o refresh periódico
    setPauseUntilMs(Date.now() + 5_000)
  }

  const handleChangeStatus = async (orderId: string, next: OrderStatus) => {
    try {
      if (next === 'pending_payment') {
        // Fluxo exige validação de endereço/loja: abrir Drawer para confirmar
        setSelected(orderId)
        // Pausa o auto-refresh enquanto o Drawer estiver aberto
        setPauseUntilMs(Date.now() + 60_000)
        return
      } else {
        setBusyIds(prev => {
          const s = new Set(prev)
          s.add(orderId)
          return s
        })
        try {
          await setOrderStatus(orderId, next)
        } finally {
          setBusyIds(prev => {
            const s = new Set(prev)
            s.delete(orderId)
            return s
          })
        }
      }
      fetchData()
    } catch (e: unknown) {
      console.error(e)
      setError(errMsg(e) || 'Falha ao alterar status')
    }
  }

  const handleDrawerClose = () => {
    setSelected(null)
    // Dá um fôlego de 2s e refaz o fetch ao fechar o Drawer
    setPauseUntilMs(Date.now() + 2_000)
    fetchData()
  }

  return (
    <div className="relative px-4 md:px-6 lg:px-8 py-4 min-h-screen overflow-x-auto">
      <div className="sticky top-0 z-10 bg-white/80 backdrop-blur border-b border-neutral-200 -mx-4 md:-mx-6 lg:-mx-8 px-4 md:px-6 lg:px-8 pb-3">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold">{ui.branding?.appTitle || 'Painel Operacional'}</h1>
            <div className="mt-2">
              <FiltersBar status={status} search={search} limit={limit} onChange={onChangeFilters} />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              className="text-xs md:text-sm px-3 py-1 rounded border border-neutral-300 bg-white hover:bg-neutral-50 text-neutral-700"
              onClick={() => {
                setPauseUntilMs(Date.now() + 2_000)
                fetchData()
              }}
            >
              Atualizar agora
            </button>
            <button
              className="text-xs md:text-sm px-3 py-1 rounded border border-neutral-300 bg-white hover:bg-neutral-50 text-neutral-700"
              onClick={() => {
                const next = !compact
                setCompact(next)
                try { localStorage.setItem('atendeja.ui.compact', next ? '1' : '0') } catch { void 0 }
              }}
            >
              {compact ? 'Visualização Padrão' : 'Visualização Compacta'}
            </button>
            <div className="flex items-center gap-1 text-xs md:text-sm">
              <label className="text-gray-600">Colunas</label>
              <select
                className="border border-neutral-300 rounded px-2 py-1 bg-white text-neutral-700 hover:bg-neutral-50"
                value={targetCols}
                onChange={(e) => {
                  const v = Number(e.target.value)
                  setTargetCols(v)
                  try { localStorage.setItem('atendeja.ui.targetCols', String(v)) } catch { void 0 }
                }}
              >
                <option value={5}>5</option>
                <option value={6}>6</option>
                <option value={7}>7</option>
                <option value={8}>8</option>
              </select>
            </div>
          </div>
        </div>
        {error && <div className="mt-2 text-sm text-red-700">{error}</div>}
        {loading && <div className="mt-2 text-sm text-gray-600">Carregando...</div>}
      </div>
      <div
        ref={boardRef}
        className="flex flex-row gap-4 md:gap-6 lg:gap-8 mt-4"
        data-testid="kanban-board"
      >
        {COLUMNS.map((col) => (
          <div
            key={col.key}
            className={`bg-gray-50 border rounded p-2 flex-none`}
            style={{ width: `${colWidth}px` }}
            data-testid={`col-${col.key}`}
          >
            <div className="font-semibold text-sm mb-2" data-testid={`col-header-${col.key}`}>
              {col.title} ({(groups.get(col.key) || []).length})
            </div>
            <div className="flex flex-col gap-2">
              {(groups.get(col.key) || []).map((o) => (
                <OrderCard
                  key={o.id}
                  order={o}
                  compact={compact}
                  busy={busyIds.has(String(o.id))}
                  onChangeStatus={handleChangeStatus}
                  onOpen={(id) => setSelected(id)}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
      {selected && <OrderDrawer orderId={selected} onClose={handleDrawerClose} />}
    </div>
  )
}
