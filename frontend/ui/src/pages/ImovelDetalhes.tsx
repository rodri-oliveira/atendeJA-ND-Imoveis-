import React, { useEffect, useState, useMemo } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiFetch, isAuthenticated } from '../lib/auth'

interface Imagem {
  id: number
  url: string
  is_capa: boolean
  ordem: number
}

interface Detalhes {
  id: number
  titulo: string
  descricao?: string | null
  tipo: 'apartment' | 'house' | string
  finalidade: 'sale' | 'rent' | string
  preco: number
  cidade: string
  estado: string
  bairro?: string | null
  dormitorios?: number | null
  banheiros?: number | null
  suites?: number | null
  vagas?: number | null
  area_total?: number | null
  area_util?: number | null
  imagens: Imagem[]
}

export default function ImovelDetalhes() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [isAdmin, setIsAdmin] = useState(false)
  const [data, setData] = useState<Detalhes | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [mainImage, setMainImage] = useState<Imagem | null>(null)

  // Helper: aceita URLs relativas, localhost e IPs (backend já normaliza externas)
  const toDirect = (url?: string | null) => {
    if (!url) return ''
    try {
      const u = String(url)
      if (u.startsWith('/')) return u
      if (u.startsWith('http://') || u.startsWith('https://')) {
        const parsed = new URL(u)
        const host = parsed.hostname || ''
        // aceita localhost/IP ou host com ponto
        const isIPv4 = /^\d{1,3}(?:\.\d{1,3}){3}$/.test(host)
        if (host === 'localhost' || host === '::1' || isIPv4 || host.includes('.')) return u
      }
      return ''
    } catch {
      return ''
    }
  }

  async function fetchDetails() {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/re/imoveis/${encodeURIComponent(id)}/detalhes`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const js = await res.json();
      setData(js);
      if (js.imagens && js.imagens.length > 0) {
        const cover = js.imagens.find((i: Imagem) => i.is_capa) || js.imagens[0];
        setMainImage(cover);
      }
    } catch (e: unknown) {
      const err = e as Error;
      setError(err?.message || 'erro');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchDetails()
    // Descobre papel do usuário via backend (JWT)
    ;(async () => {
      try {
        if (!isAuthenticated()) { setIsAdmin(false); return }
        const res = await apiFetch('/api/auth/me')
        if (!res.ok) { setIsAdmin(false); return }
        const js = await res.json()
        setIsAdmin(js?.role === 'admin')
      } catch {
        setIsAdmin(false)
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  // Ações admin
  async function onSoftDelete() {
    if (!id) return
    if (!confirm('Arquivar este imóvel? Ele ficará inativo.')) return
    const res = await apiFetch(`/api/admin/re/imoveis/${encodeURIComponent(id)}`, { method: 'DELETE' })
    if (res.ok) navigate('/imoveis')
  }

  async function onHardDelete() {
    if (!id) return
    if (!confirm('Excluir PERMANENTEMENTE este imóvel e seus arquivos? Esta ação não pode ser desfeita.')) return
    const res = await apiFetch(`/api/admin/re/imoveis/${encodeURIComponent(id)}/hard`, { method: 'DELETE' })
    if (res.ok) navigate('/imoveis')
  }


  const characteristics = useMemo(() => {
    if (!data) return [];
    return [
      { icon: '🛏️', label: 'Dormitórios', value: data.dormitorios },
      { icon: '🛁', label: 'Banheiros', value: data.banheiros },
      { icon: '🚿', label: 'Suítes', value: data.suites },
      { icon: '🚗', label: 'Vagas', value: data.vagas },
      { icon: '🌳', label: 'Área Total', value: data.area_total, suffix: ' m²' },
      { icon: '🏠', label: 'Área Útil', value: data.area_util, suffix: ' m²' },
    ].filter(c => typeof c.value === 'number');
  }, [data]);

  return (
    <section className="space-y-6">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <Link to="/imoveis" className="inline-flex items-center gap-1 text-primary-600 hover:underline focus:outline-none focus:ring-2 focus:ring-primary-300 rounded px-1">
            <span aria-hidden>←</span>
            <span>Voltar para a lista</span>
          </Link>
        </div>
      </header>

      {loading && <div className="text-center py-12 text-slate-500">Carregando detalhes do imóvel...</div>}
      {error && <div className="card text-red-600">Erro ao carregar imóvel: {error}</div>}

      {!loading && !error && data && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Coluna Principal (Esquerda) */}
          <div className="lg:col-span-2 space-y-6">
            {/* Galeria de Imagens Hero */}
            <div className="space-y-3">
              <div className="aspect-[16/10] bg-slate-100 rounded-xl overflow-hidden border">
                {mainImage && <img src={toDirect(mainImage.url)} alt="Imagem principal do imóvel" className="w-full h-full object-cover" />}
              </div>
              <div className="grid grid-cols-5 md:grid-cols-8 gap-2">
                {data.imagens.map(img => (
                  <button key={img.id} onClick={() => setMainImage(img)} className={`aspect-square bg-slate-100 rounded-lg overflow-hidden border-2 transition-all ${mainImage?.id === img.id ? 'border-primary-500' : 'border-transparent hover:border-slate-300'}`}>
                    <img src={toDirect(img.url)} alt={`Imagem ${img.id}`} className="w-full h-full object-cover" />
                  </button>
                ))}
              </div>
            </div>

            {/* Título e Localização */}
            <div>
              <h1 className="text-3xl font-bold text-slate-900">{data.titulo}</h1>
              <p className="text-slate-600 mt-1">{data.bairro}, {data.cidade} - {data.estado}</p>
            </div>

            {/* Características com Ícones */}
            <div className="card">
              <h2 className="card-header">Características</h2>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mt-4">
                {characteristics.map(char => (
                  <div key={char.label} className="flex items-center gap-3">
                    <span className="text-2xl">{char.icon}</span>
                    <div>
                      <div className="text-sm text-slate-600">{char.label}</div>
                      <div className="font-semibold text-slate-800">{char.value}{char.suffix || ''}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Descrição */}
            {data.descricao && (
              <div className="card">
                <h2 className="card-header">Descrição</h2>
                <p className="text-slate-700 mt-4 whitespace-pre-wrap">{data.descricao}</p>
              </div>
            )}
          </div>

          {/* Coluna Lateral (Direita) */}
          <div className="lg:col-span-1">
            <div className="sticky top-4 space-y-4">
              {/* Ações do Admin */}
              {isAdmin && (
                <div className="card">
                  <h2 className="card-header">Ações do Administrador</h2>
                  <div className="flex flex-col gap-2 mt-4">
                    <button className="btn btn-secondary" onClick={() => navigate(`/imoveis/${id}/editar`)}>Editar Imóvel</button>
                    <button className="btn btn-warning" onClick={onSoftDelete}>Arquivar Imóvel</button>
                    <button className="btn btn-danger" onClick={onHardDelete}>Excluir Permanentemente</button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
