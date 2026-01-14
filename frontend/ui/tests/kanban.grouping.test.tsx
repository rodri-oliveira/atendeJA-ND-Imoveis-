/* @vitest-environment jsdom */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import React from 'react'
import { render, screen, within } from '@testing-library/react'
import KanbanPage from '../src/pages/KanbanPage'
import { ConfigProvider } from '../src/config/provider'

const g: any = globalThis as any

describe('KanbanPage - agrupamento por coluna', () => {
  beforeEach(() => {
    // container explícito anexado ao body
    const root = document.createElement('div')
    root.setAttribute('id', 'root')
    document.body.appendChild(root)

    g.fetch = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/config.json')) {
        return new Response(
          JSON.stringify({
            branding: { appTitle: 'Painel Operacional' },
            kanban: {
              columns: [
                { status: 'draft', title: 'Rascunho' },
                { status: 'in_kitchen', title: 'Em preparo' },
              ],
            },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.includes('/orders') && (!init || init.method === 'GET')) {
        return new Response(
          JSON.stringify([
            { id: '10', status: 'draft', total_amount: 1 },
            { id: '11', status: 'in_kitchen', total_amount: 2 },
            { id: '12', status: 'in_kitchen', total_amount: 3 },
          ]),
          { status: 200 }
        )
      }
      return new Response('', { status: 404 })
    })
    if (typeof (g as any).window !== 'undefined') {
      ;(g as any).window.ENV = { API_BASE_URL: 'http://api:8000' }
    }
  })

  it('renderiza cards nas colunas corretas', async () => {
    const container = document.getElementById('root') as HTMLElement
    render(
      <ConfigProvider>
        <KanbanPage />
      </ConfigProvider>,
      { container }
    )

    // Coluna de rascunho com pedido #10
    const colDraft = await screen.findByTestId('col-draft')
    expect(within(colDraft).getAllByText(/Total: R\$/).length).toBeGreaterThan(0)

    // Coluna em preparo com pedidos #11 e #12
    const colKitchen = screen.getByTestId('col-in_kitchen')
    // Deve haver pelo menos 2 cards com Total
    const totalsInKitchen = within(colKitchen).getAllByText(/Total: R\$/)
    expect(totalsInKitchen.length).toBeGreaterThanOrEqual(2)
  })
})
