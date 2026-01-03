export type ColumnSpec = {
  status: string
  title: string
}

export type ActionSpec = {
  label: string
  next: string
}

export type Branding = {
  appTitle?: string
  tenantName?: string
}

export type ApiConfig = {
  tenantId?: number
  superAdminKey?: string
}

export type UIConfig = {
  branding?: Branding
  api?: ApiConfig
  kanban: {
    columns: ColumnSpec[]
    actions?: Record<string, ActionSpec[]>
  }
  ui?: {
    compactDefault?: boolean
    zoomDefault?: number
    columnWidth?: number
    targetColumnsDefault?: number
    columnWidthMin?: number
    columnWidthMax?: number
  }
}

export const defaultConfig: UIConfig = {
  branding: { appTitle: 'Painel Operacional', tenantName: 'ND Imóveis' },
  api: {},
  kanban: {
    columns: [
      { status: 'new', title: 'Novo' },
      { status: 'contacted', title: 'Contato feito' },
      { status: 'qualified', title: 'Qualificado' },
      { status: 'visit_scheduled', title: 'Visita marcada' },
      { status: 'proposal', title: 'Proposta' },
      { status: 'won', title: 'Fechado' },
      { status: 'lost', title: 'Perdido' },
    ],
    actions: {
      new: [
        { label: 'Marcar contato feito', next: 'contacted' },
        { label: 'Marcar perdido', next: 'lost' },
      ],
      contacted: [
        { label: 'Qualificar', next: 'qualified' },
        { label: 'Marcar perdido', next: 'lost' },
      ],
      qualified: [
        { label: 'Marcar visita', next: 'visit_scheduled' },
        { label: 'Marcar perdido', next: 'lost' },
      ],
      visit_scheduled: [
        { label: 'Enviar proposta', next: 'proposal' },
        { label: 'Marcar perdido', next: 'lost' },
      ],
      proposal: [
        { label: 'Fechar', next: 'won' },
        { label: 'Marcar perdido', next: 'lost' },
      ],
    },
  },
  ui: {
    compactDefault: false,
    zoomDefault: 1,
    columnWidth: 280,
    targetColumnsDefault: 7,
    columnWidthMin: 220,
    columnWidthMax: 320,
  },
}
