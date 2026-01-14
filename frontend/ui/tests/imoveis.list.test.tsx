// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ImoveisList from '../src/pages/ImoveisList'

const mockImoveis = [
  {
    id: 1,
    titulo: 'Apto 2 dorm SP',
    tipo: 'apartment',
    finalidade: 'rent',
    preco: 3000,
    cidade: 'São Paulo',
    estado: 'SP',
    dormitorios: 2,
    ativo: true,
  },
]

describe('ImoveisList', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renderiza título e carrega lista', async () => {
    const g: any = globalThis as any
    g.fetch = vi.fn(async (url: string) => {
      const u = String(url)
      if (u.includes('/api/re/imoveis/type-counts')) {
        return new Response(JSON.stringify({ type_counts: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (u.includes('/api/re/imoveis')) {
        return new Response(JSON.stringify(mockImoveis), {
          status: 200,
          headers: { 'Content-Type': 'application/json', 'X-Total-Count': '1' },
        })
      }
      return new Response('', { status: 404 })
    })

    render(
      <MemoryRouter initialEntries={["/imoveis"]}>
        <ImoveisList />
      </MemoryRouter>
    )

    // título
    const title = await screen.findByText('Imóveis')
    expect(title).toBeTruthy()

    // card carregado
    await waitFor(() => {
      expect(screen.getByText('Apto 2 dorm SP')).toBeTruthy()
      expect(screen.getByText(/R\$\s*3\.000/)).toBeTruthy()
    })
  })
})
