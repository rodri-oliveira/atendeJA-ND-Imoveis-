/* @vitest-environment jsdom */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import KanbanPage from '../src/pages/KanbanPage'
import { ConfigProvider } from '../src/config/provider'

const g: any = globalThis as any

describe('KanbanPage - ação de mudar status', () => {
  beforeEach(() => {
    const root = document.createElement('div')
    root.setAttribute('id', 'root')
    document.body.appendChild(root)

    // Primeiro GET retorna um pedido em paid (#1)
    // Após PATCH, GET subsequente retorna o mesmo pedido em in_kitchen
    let calls = 0
    g.fetch = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/config.json')) {
        return new Response(
          JSON.stringify({
            branding: { appTitle: 'Painel Operacional' },
            kanban: {
              columns: [
                { status: 'paid', title: 'Pago' },
                { status: 'in_kitchen', title: 'Em preparo' },
              ],
              actions: {
                paid: [{ label: 'Marcar em preparo', next: 'in_kitchen' }],
              },
            },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.includes('/orders') && (!init || init.method === 'GET')) {
        calls++
        if (calls === 1) {
          return new Response(JSON.stringify([{ id: '1', status: 'paid', total_amount: 10 }]), { status: 200 })
        }
        return new Response(JSON.stringify([{ id: '1', status: 'in_kitchen', total_amount: 10 }]), { status: 200 })
      }
      if (url.includes('/status') && init?.method === 'PATCH') {
        return new Response(JSON.stringify({ order_id: '1', status: 'in_kitchen' }), { status: 200 })
      }
      return new Response('', { status: 404 })
    })
    if (typeof (g as any).window !== 'undefined') {
      ;(g as any).window.ENV = { API_BASE_URL: 'http://api:8000' }
    }
  })

  it('dispara PATCH (paid -> in_kitchen) e atualiza a coluna', async () => {
    const container = document.getElementById('root') as HTMLElement
    render(
      <ConfigProvider>
        <KanbanPage />
      </ConfigProvider>,
      { container }
    )

    // Botão de ação aparece no card do status paid
    const button = await screen.findByRole('button', { name: /Marcar em preparo/i })
    fireEvent.click(button)

    // Verifica que PATCH foi chamado
    await waitFor(() => {
      const calls = (g.fetch as any).mock.calls
      const hasPatch = calls.some((c: any[]) => String(c[0]).includes('/status') && c[1]?.method === 'PATCH')
      expect(hasPatch).toBe(true)
    })

    // Após refetch, o card deve aparecer na coluna in_kitchen
    await waitFor(() => {
      const kitchenHeaders = screen.getAllByTestId('col-header-in_kitchen')
      expect(kitchenHeaders.length).toBeGreaterThan(0)
    })
  })
})
