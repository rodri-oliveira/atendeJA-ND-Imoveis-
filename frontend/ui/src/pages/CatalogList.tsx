import React, { useEffect, useState } from 'react';
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
  attributes: VehicleAttributes;
  is_active: boolean;
}

export default function CatalogList() {
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [baseUrl, setBaseUrl] = useState('https://mogimaisveiculos.com.br/');
  const [maxListings, setMaxListings] = useState(30);
  const [maxListingPages, setMaxListingPages] = useState(5);
  const [busy, setBusy] = useState(false);
  const [discoverOut, setDiscoverOut] = useState<Record<string, unknown> | null>(null);
  const [runOut, setRunOut] = useState<Record<string, unknown> | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      await loadMe();
      await reloadItems();
    })();
  }, []);

  async function loadMe() {
    try {
      const res = await apiFetch('/api/auth/me');
      if (!res.ok) return;
      const js = (await res.json()) as { role?: string };
      setRole(js.role || null);
    } catch {
      // ignore
    }
  }

  async function reloadItems() {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/catalog/items?item_type_key=vehicle&limit=200');
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

  async function onDiscover() {
    setBusy(true);
    setActionError(null);
    setDiscoverOut(null);
    try {
      const res = await apiFetch('/api/admin/catalog/ingestion/discover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_url: baseUrl,
          max_listing_pages: maxListingPages,
          max_detail_links: 400,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const js = await res.json();
      setDiscoverOut(js);
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : 'Erro ao executar discovery');
    } finally {
      setBusy(false);
    }
  }

  async function onRun() {
    setBusy(true);
    setActionError(null);
    setRunOut(null);
    try {
      const res = await apiFetch('/api/admin/catalog/ingestion/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_url: baseUrl,
          max_listings: maxListings,
          timeout_seconds: 10,
          max_listing_pages: maxListingPages,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const js = await res.json();
      setRunOut(js);
      await reloadItems();
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : 'Erro ao executar ingestão');
    } finally {
      setBusy(false);
    }
  }

  const formatPrice = (value: number | null | undefined) => {
    if (value === null || value === undefined) return '-';
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
  };

  return (
    <section className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Catálogo de Veículos</h1>
          <p className="text-sm text-slate-600 mt-1">Veículos ingeridos disponíveis no tenant atual.</p>
        </div>
      </header>

      {role === 'admin' && (
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="md:col-span-2">
            <label className="block text-xs font-semibold text-slate-600">Base URL</label>
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="https://exemplo.com.br/"
              disabled={busy}
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600">Max páginas de listagem</label>
            <input
              type="number"
              value={maxListingPages}
              onChange={(e) => setMaxListingPages(Number(e.target.value || 0))}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              min={0}
              max={20}
              disabled={busy}
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-600">Max anúncios (run)</label>
            <input
              type="number"
              value={maxListings}
              onChange={(e) => setMaxListings(Number(e.target.value || 0))}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              min={1}
              max={200}
              disabled={busy}
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onDiscover}
            disabled={busy}
            className="text-xs px-3 py-2 rounded-lg bg-slate-800 text-white hover:bg-slate-700 disabled:opacity-50"
          >
            Discover
          </button>
          <button
            onClick={onRun}
            disabled={busy}
            className="text-xs px-3 py-2 rounded-lg bg-primary-600 text-white hover:bg-primary-500 disabled:opacity-50"
          >
            Run
          </button>
          <button
            onClick={reloadItems}
            disabled={busy}
            className="text-xs px-3 py-2 rounded-lg bg-slate-200 text-slate-800 hover:bg-slate-300 disabled:opacity-50"
          >
            Recarregar lista
          </button>
          {busy && <span className="text-xs text-slate-500">Processando...</span>}
        </div>

        {actionError && <div className="text-sm text-red-600">Erro: {actionError}</div>}

        {discoverOut && (
          <pre className="text-xs bg-slate-50 border border-slate-200 rounded-lg p-3 overflow-auto">
            {JSON.stringify(discoverOut, null, 2)}
          </pre>
        )}

        {runOut && (
          <pre className="text-xs bg-slate-50 border border-slate-200 rounded-lg p-3 overflow-auto">
            {JSON.stringify(runOut, null, 2)}
          </pre>
        )}
      </div>
      )}

      {loading && <p>Carregando...</p>}
      {error && <p className="text-red-500">Erro: {error}</p>}

      {!loading && !error && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm text-left text-slate-500">
            <thead className="text-xs text-slate-700 uppercase bg-slate-50">
              <tr>
                <th scope="col" className="px-6 py-3">ID</th>
                <th scope="col" className="px-6 py-3">Título</th>
                <th scope="col" className="px-6 py-3">Preço</th>
                <th scope="col" className="px-6 py-3">Ano</th>
                <th scope="col" className="px-6 py-3">KM</th>
                <th scope="col" className="px-6 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="bg-white border-b hover:bg-slate-50">
                  <td className="px-6 py-4 font-medium text-slate-900">{item.id}</td>
                  <td className="px-6 py-4">{item.title}</td>
                  <td className="px-6 py-4">{formatPrice(item.attributes.price)}</td>
                  <td className="px-6 py-4">{item.attributes.year || '-'}</td>
                  <td className="px-6 py-4">{item.attributes.km || '-'}</td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${item.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                      {item.is_active ? 'Ativo' : 'Inativo'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {items.length === 0 && (
            <div className="p-6 text-center text-slate-500">
              Nenhum veículo encontrado.
            </div>
          )}
        </div>
      )}
    </section>
  );
}
