/* @vitest-environment jsdom */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import React from 'react'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import OrderDrawer from '../src/components/OrderDrawer'

const g: any = globalThis as any

describe('OrderDrawer', () => {
  beforeEach(() => {
    // container explícito
    const root = document.createElement('div')
    root.setAttribute('id', 'root')
    document.body.appendChild(root)

    g.fetch = vi.fn(async (url: string) => {
      if (url.endsWith('/orders/1')) {
        return new Response(
          JSON.stringify({
            order_id: 1,
            status: 'draft',
            total_items: 2,
            delivery_fee: 0,
            total_amount: 10,
            delivery_address: { city: 'São Paulo', street: 'Rua A' },
            items: [
              { id: 1, menu_item_id: 100, qty: 1, unit_price: 5 },
              { id: 2, menu_item_id: 101, qty: 1, unit_price: 5 },
            ],
          }),
          { status: 200 }
        )
      }
      if (url.endsWith('/orders/1/events')) {
        return new Response(
          JSON.stringify([
            { id: 1, order_id: 1, from_status: 'draft', to_status: 'draft', created_at: '2024-01-01T00:00:00Z' },
          ]),
          { status: 200 }
        )
      }
      if (url.endsWith('/orders/1/relation')) {
        return new Response(JSON.stringify({ order_id: 1, source_order_id: null }), { status: 200 })
      }
      if (url.endsWith('/orders/1/reorders')) {
        return new Response(JSON.stringify([]), { status: 200 })
      }
      return new Response('', { status: 404 })
    })

    if (typeof (g as any).window !== 'undefined') {
      ;(g as any).window.ENV = { API_BASE_URL: '/api' }
    }
  })

  it('aplica máscara e validação de CEP, desabilitando botão quando inválido', async () => {
    const onClose = vi.fn()
    const container = document.getElementById('root') as HTMLElement

    g.fetch = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/orders/1') && (!init || init.method === 'GET')) {
        return new Response(
          JSON.stringify({ order_id: 1, status: 'draft', items: [], delivery_address: {} }),
          { status: 200 }
        )
      }
      if (url.endsWith('/orders/1/events')) return new Response(JSON.stringify([]), { status: 200 })
      if (url.endsWith('/orders/1/relation')) return new Response(JSON.stringify({ order_id: 1, source_order_id: null }), { status: 200 })
      if (url.endsWith('/orders/1/reorders')) return new Response(JSON.stringify([]), { status: 200 })
      return new Response('', { status: 404 })
    })
    render(<OrderDrawer orderId="1" onClose={onClose} />, { container })
    await screen.findByText(/Resumo/i)

    const cepInput = (await screen.findByRole('textbox', { name: /cep/i })) as HTMLInputElement
    // cep parcial inválido
    fireEvent.change(cepInput, { target: { value: '123' } })
    expect(cepInput.value).toBe('123')
    expect(screen.getByText('CEP deve ser 00000-000')).toBeTruthy()

    // máscara ao digitar 8 dígitos
    fireEvent.change(cepInput, { target: { value: '12345678' } })
    expect(cepInput.value).toBe('12345-678')

    // botão salvar desabilitado enquanto existir erro de validação (faltam outros campos obrigatórios)
    const btnSalvar = screen.getByText('Salvar endereço') as HTMLButtonElement
    expect(btnSalvar.disabled).toBe(true)
  })

  it('valida UF com 2 letras e transforma para maiúsculas', async () => {
    const onClose = vi.fn()
    const container = document.getElementById('root') as HTMLElement

    g.fetch = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes('/orders/1') && (!init || init.method === 'GET') && !url.includes('/events') && !url.includes('/relation') && !url.includes('/reorders')) {
        return new Response(
          JSON.stringify({ order_id: 1, status: 'draft', items: [], delivery_address: {} }),
          { status: 200 }
        )
      }
      if (url.includes('/orders/1/events')) return new Response(JSON.stringify([]), { status: 200 })
      if (url.includes('/orders/1/relation')) return new Response(JSON.stringify({ order_id: 1, source_order_id: null }), { status: 200 })
      if (url.includes('/orders/1/reorders')) return new Response(JSON.stringify([]), { status: 200 })
      return new Response('', { status: 404 })
    })
    ;(g as any).window.ENV = { API_BASE_URL: '/api' }

    render(<OrderDrawer orderId="1" onClose={onClose} />, { container })
    await screen.findByText(/Resumo/i)

    const ufInput = (await screen.findByRole('textbox', { name: /estado/i })) as HTMLInputElement
    fireEvent.change(ufInput, { target: { value: 's' } })
    expect(screen.getByText('UF deve ter 2 letras')).toBeTruthy()

    fireEvent.change(ufInput, { target: { value: 'sp' } })
    expect(ufInput.value).toBe('SP')
  })

  it('carrega e exibe detalhes do pedido', async () => {
    const onClose = vi.fn()
    const container = document.getElementById('root') as HTMLElement
    render(<OrderDrawer orderId="1" onClose={onClose} />, { container })
    // detalhes
    await waitFor(() => {
      expect(screen.getByText(/Resumo/i)).toBeTruthy()
      expect(screen.getByText(/Total: R\$ 10.00/i)).toBeTruthy()
      expect(screen.getByText(/Eventos/i)).toBeTruthy()
    })
  })

  it('fecha ao clicar no overlay', async () => {
    const onClose = vi.fn()
    const container = document.getElementById('root') as HTMLElement
    render(<OrderDrawer orderId="1" onClose={onClose} />, { container })
    await screen.findByText(/Resumo/i)
    const overlay = document.querySelector('.fixed.inset-0.z-50 > .absolute.inset-0') as HTMLElement
    fireEvent.click(overlay)
    expect(onClose).toHaveBeenCalled()
  })

  it('fecha ao pressionar ESC', async () => {
    const onClose = vi.fn()
    const container = document.getElementById('root') as HTMLElement
    render(<OrderDrawer orderId="1" onClose={onClose} />, { container })
    await screen.findByText(/Resumo/i)
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })

  it('confirma pedido com sucesso e atualiza detalhes', async () => {
    const onClose = vi.fn()
    const container = document.getElementById('root') as HTMLElement

    // Mock com estado para simular mudança de status após confirmar
    let confirmed = false
    g.fetch = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.includes('/orders/1?op=confirm') && init?.method === 'PATCH') {
        confirmed = true
        return new Response(JSON.stringify({ ok: true }), { status: 200 })
      }
      if (url.endsWith('/orders/1') && (!init || init.method === 'GET')) {
        if (!confirmed) {
          return new Response(
            JSON.stringify({
              order_id: 1,
              status: 'draft',
              total_items: 2,
              delivery_fee: 0,
              total_amount: 10,
              delivery_address: {
                street: 'Rua A',
                number: '123',
                district: 'Centro',
                city: 'São Paulo',
                state: 'SP',
                cep: '01000-000'
              },
              items: [
                { id: 1, menu_item_id: 100, qty: 1, unit_price: 5 },
                { id: 2, menu_item_id: 101, qty: 1, unit_price: 5 },
              ],
            }),
            { status: 200 }
          )
        }
        return new Response(
          JSON.stringify({ order_id: 1, status: 'pending_payment', items: [] }),
          { status: 200 }
        )
      }
      if (url.endsWith('/orders/1/events')) return new Response(JSON.stringify([]), { status: 200 })
      if (url.endsWith('/orders/1/relation')) return new Response(JSON.stringify({ order_id: 1, source_order_id: null }), { status: 200 })
      if (url.endsWith('/orders/1/reorders')) return new Response(JSON.stringify([]), { status: 200 })
      return new Response('', { status: 404 })
    })
    ;(g as any).window.ENV = { API_BASE_URL: '/api' }

    render(<OrderDrawer orderId="1" onClose={onClose} />, { container })
    await screen.findByText(/Resumo/i)
    const btn = screen.getByText(/Confirmar pedido/i)
    fireEvent.click(btn)
    await waitFor(() => {
      expect(screen.getByText(/Status:/i).textContent).toContain('pending_payment')
    })
  })

  it('exibe erro address_required ao confirmar sem endereço válido', async () => {
    const onClose = vi.fn()
    const container = document.getElementById('root') as HTMLElement

    g.fetch = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/orders/1') && (!init || init.method === 'GET')) {
        return new Response(
          JSON.stringify({ order_id: 1, status: 'draft', items: [], delivery_address: {} }),
          { status: 200 }
        )
      }
      if (url.includes('/orders/1?op=confirm') && init?.method === 'PATCH') {
        return new Response(
          JSON.stringify({ detail: 'address_required' }),
          { status: 400, headers: { 'Content-Type': 'application/json' } }
        )
      }
      if (url.endsWith('/orders/1/events')) return new Response(JSON.stringify([]), { status: 200 })
      if (url.endsWith('/orders/1/relation')) return new Response(JSON.stringify({ order_id: 1, source_order_id: null }), { status: 200 })
      if (url.endsWith('/orders/1/reorders')) return new Response(JSON.stringify([]), { status: 200 })
      return new Response('', { status: 404 })
    })
    ;(g as any).window.ENV = { API_BASE_URL: '/api' }

    render(<OrderDrawer orderId="1" onClose={onClose} />, { container })
    await screen.findByText(/Resumo/i)
    const btn = screen.getByText(/Confirmar pedido/i)
    fireEvent.click(btn)

    await waitFor(() => {
      const err = screen.getByText(/address_required/i)
      expect(err).toBeTruthy()
    })
  })
})
