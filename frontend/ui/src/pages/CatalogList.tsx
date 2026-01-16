import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch } from '../lib/auth';

interface VehicleAttributes {
  price?: number;
  year?: number;
  km?: number;
  make?: string;
  model?: string;
  transmission?: string;
  fuel?: string;
}

interface CatalogItem {
  id: number;
  title: string;
  description?: string | null;
  attributes: VehicleAttributes;
  is_active: boolean;
  media?: Array<{ id: number; kind: string; url: string; sort_order: number }>;
}

export default function CatalogList() {
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);

  const repeatedImageUrls = useMemo(() => {
    const counts = new Map<string, number>();
    for (const it of items) {
      for (const m of it.media || []) {
        if (m.kind !== 'image' || !m.url) continue;
        const u = String(m.url).trim();
        if (!u) continue;
        counts.set(u, (counts.get(u) || 0) + 1);
      }
    }

    const repeated = new Set<string>();
    // Heurística: se a mesma URL aparece em muitos itens, é asset global (logo/banner)
    for (const [u, c] of counts.entries()) {
      if (c >= 3) repeated.add(u);
    }
    return repeated;
  }, [items]);

  useEffect(() => {
    void (async () => {
      await loadRole();
      await reloadItems();
    })();
  }, []);

  async function loadRole() {
    try {
      const res = await apiFetch('/api/auth/me');
      if (!res.ok) {
        setIsAdmin(false);
        return;
      }
      const js = (await res.json()) as { role?: string };
      setIsAdmin(js?.role === 'admin');
    } catch {
      setIsAdmin(false);
    }
  }

  async function reloadItems() {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/admin/catalog/items?item_type_key=vehicle&limit=200');
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();
      setItems(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar itens do catálogo');
    } finally {
      setLoading(false);
    }
  }

  const formatPrice = (value: number | null | undefined) => {
    if (value === null || value === undefined) return '-';
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
  };

  const isBadImageUrl = (url: string): boolean => {
    const u = String(url || '').trim().toLowerCase();
    if (!u) return true;
    if (u.startsWith('data:')) return true;
    if (u.endsWith('.svg') || u.endsWith('.ico')) return true;
    const bad = [
      'logo',
      'favicon',
      'sprite',
      'icon',
      'brand',
      'banner',
      'header',
      'footer',
      'navbar',
      'menu',
      'social',
      'whatsapp',
      'facebook',
      'instagram',
      'tiktok',
      'placeholder',
      'noimage',
      'default',
    ];
    return bad.some((k) => u.includes(k));
  };

  const getThumbUrl = (item: CatalogItem): string | null => {
    const m = (item.media || []).find(
      (x) => x.kind === 'image' && !!x.url && !isBadImageUrl(x.url) && !repeatedImageUrls.has(String(x.url).trim())
    );
    return m?.url || null;
  };

  return (
    <section className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Catálogo de Veículos</h1>
          <p className="text-sm text-slate-600 mt-1">Veículos ingeridos disponíveis no tenant atual.</p>
        </div>
        <div className="flex items-center gap-2">
          {isAdmin && (
            <Link
              to="/catalog/vehicles/novo"
              className="text-xs px-3 py-2 rounded-lg bg-primary-600 text-white hover:bg-primary-700"
            >
              Cadastrar veículo
            </Link>
          )}
          <button
            onClick={reloadItems}
            className="text-xs px-3 py-2 rounded-lg bg-slate-200 text-slate-800 hover:bg-slate-300 disabled:opacity-50"
            disabled={loading}
          >
            Recarregar lista
          </button>
        </div>
      </header>

      {loading && <p>Carregando...</p>}
      {error && <p className="text-red-500">Erro: {error}</p>}

      {!loading && !error && items.length === 0 && (
        <div className="text-center py-12">
          <div className="text-slate-400 text-lg mb-2">Nenhum veículo encontrado</div>
          <div className="text-sm text-slate-500">Rode a ingestão via script e tente novamente.</div>
        </div>
      )}

      {!loading && !error && items.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {items.map((item, index) => (
            <article
              key={item.id}
              className="group rounded-xl border border-slate-200 bg-white shadow-card hover:shadow-hover transition-all duration-300 overflow-hidden hover-lift card-entrance"
              style={{ animationDelay: `${index * 0.05}s` }}
            >
              <div className="h-48 relative overflow-hidden bg-gradient-to-br from-slate-100 to-slate-200">
                {getThumbUrl(item) ? (
                  <img
                    src={getThumbUrl(item) as string}
                    alt={item.title}
                    className="absolute inset-0 w-full h-full object-cover"
                    loading="lazy"
                    onError={(e) => {
                      const el = e.currentTarget as HTMLImageElement;
                      el.style.display = 'none';
                    }}
                  />
                ) : null}
                <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent"></div>
                <div className="absolute top-3 left-3">
                  <span
                    className={`px-2 py-1 rounded-full text-xs font-medium ${
                      item.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'
                    }`}
                  >
                    {item.is_active ? 'Ativo' : 'Inativo'}
                  </span>
                </div>
                {item.attributes?.year ? (
                  <div className="absolute top-3 right-3">
                    <span className="px-2 py-1 rounded-full text-xs font-medium bg-white/90 text-slate-700">
                      {item.attributes.year}
                    </span>
                  </div>
                ) : null}
              </div>

              <div className="p-5 space-y-4">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900 group-hover:text-primary-600 transition-colors duration-200 line-clamp-2">
                    {item.title}
                  </h2>
                  {(item.attributes?.make || item.attributes?.model) && (
                    <div className="text-sm text-slate-500 mt-1">
                      {(item.attributes?.make || '').trim()} {(item.attributes?.model || '').trim()}
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between">
                  <div className="text-2xl font-bold text-primary-600">
                    {item.attributes?.price ? formatPrice(item.attributes.price) : 'Consulte'}
                  </div>
                  {typeof item.attributes?.km === 'number' && (
                    <div className="text-sm text-slate-500">
                      {new Intl.NumberFormat('pt-BR').format(item.attributes.km)} km
                    </div>
                  )}
                </div>

                {item.description && (
                  <div className="text-xs text-slate-500 line-clamp-2">{item.description}</div>
                )}

                <div className="pt-2">
                  <Link
                    to={`/catalog/vehicles/${item.id}`}
                    className="block w-full text-center px-4 py-2.5 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-all duration-200 hover-lift"
                  >
                    Ver Detalhes
                  </Link>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
