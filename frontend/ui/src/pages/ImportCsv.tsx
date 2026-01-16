import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch, isAuthenticated } from '../lib/auth'

interface ImportResult {
  processed?: number
  inserted?: number
  updated?: number
  errors?: Array<{ line?: number; message: string }>
  [k: string]: unknown
}

export default function ImportCsv() {
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [success, setSuccess] = useState(false)
  const authed = isAuthenticated()

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setResult(null)
    if (!file) {
      setError('Selecione um arquivo CSV.')
      return
    }
    if (!authed) {
      setError('Faça login para enviar (use /login).')
      return
    }
    try {
      setLoading(true)
      const fd = new FormData()
      fd.append('file', file)
      const res = await apiFetch('/api/admin/re/imoveis/import-csv', {
        method: 'POST',
        body: fd,
      })
      if (!res.ok) {
        try {
          const js = await res.json()
          throw new Error(js?.detail || js?.message || `HTTP ${res.status}`)
        } catch {
          throw new Error(`HTTP ${res.status}`)
        }
      }
      const js = await res.json()
      setResult(js)
      setSuccess(true)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Falha no upload'
      setError(msg)
      setSuccess(false)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">Importar CSV de Imóveis</h1>
        <div className="text-sm text-slate-500">Envie um arquivo .csv</div>
      </header>

      <form onSubmit={onSubmit} className="card space-y-4">
        {!authed && (
          <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3">
            Você precisa <Link to="/login" className="underline font-medium">entrar</Link> para importar CSV.
          </div>
        )}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
          <div className="flex items-center gap-4">
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="text-sm file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-primary-50 file:text-primary-700 hover:file:bg-primary-100 transition-colors"
            />
            <button
              type="submit"
              disabled={loading || !file}
              className="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Enviando...' : 'Enviar'}
            </button>
          </div>
        </div>
        <div className="text-sm text-slate-500 bg-slate-50 rounded-lg p-3">
          💡 <strong>Dica:</strong> use o arquivo de exemplo disponível no repositório (import_sample.csv)
        </div>
      </form>

      {error && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl p-4">
          ⚠️ <strong>Erro:</strong> {error}
        </div>
      )}

      {success && (
        <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-center justify-between">
          <span>✓ Importação concluída com sucesso.</span>
          <Link to="/imoveis" className="text-emerald-800 hover:text-emerald-900 font-medium transition-colors">
            Ver imóveis →
          </Link>
        </div>
      )}

      {result && (
        <div className="card space-y-4">
          <h2 className="text-lg font-semibold text-slate-900">Resultado da Importação</h2>
          <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {'processed' in result && (
              <div className="bg-slate-50 rounded-lg p-3">
                <dt className="text-sm font-medium text-slate-500">Processados</dt>
                <dd className="text-xl font-bold text-slate-900">{String(result.processed)}</dd>
              </div>
            )}
            {'inserted' in result && (
              <div className="bg-emerald-50 rounded-lg p-3">
                <dt className="text-sm font-medium text-emerald-600">Inseridos</dt>
                <dd className="text-xl font-bold text-emerald-700">{String(result.inserted)}</dd>
              </div>
            )}
            {'updated' in result && (
              <div className="bg-amber-50 rounded-lg p-3">
                <dt className="text-sm font-medium text-amber-600">Atualizados</dt>
                <dd className="text-xl font-bold text-amber-700">{String(result.updated)}</dd>
              </div>
            )}
          </dl>
          {!!result.errors?.length && (
            <div className="border-t border-slate-200 pt-4">
              <h3 className="text-sm font-semibold text-slate-900 mb-2">Erros Encontrados</h3>
              <ul className="text-sm text-red-700 space-y-1 bg-red-50 rounded-lg p-3">
                {result.errors.map((er, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-red-500">•</span>
                    <span>{er.line ? `Linha ${er.line}: ` : ''}{er.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <details className="border-t border-slate-200 pt-4">
            <summary className="text-sm text-primary-700 cursor-pointer hover:text-primary-800 font-medium transition-colors">
              Ver JSON completo
            </summary>
            <pre className="text-xs bg-slate-50 border border-slate-200 rounded-lg p-3 whitespace-pre-wrap break-all mt-2 text-slate-700">{JSON.stringify(result, null, 2)}</pre>
          </details>
        </div>
      )}
    </section>
  )
}
