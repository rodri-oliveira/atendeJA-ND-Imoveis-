import React, { useEffect } from 'react'
import { apiFetch } from '../../lib/auth'
import type { CatalogMediaOut } from './types'
import { extractErrorMessage } from './utils'

type Props = {
  itemId: number
  disabled: boolean
  media: CatalogMediaOut[]
  setMedia: (v: CatalogMediaOut[]) => void
  mediaLoading: boolean
  setMediaLoading: (v: boolean) => void
  mediaError: string | null
  setMediaError: (v: string | null) => void
  newMediaUrl: string
  setNewMediaUrl: (v: string) => void
  addingMedia: boolean
  setAddingMedia: (v: boolean) => void
}

export default function CatalogMediaEditor(props: Props) {
  const {
    itemId,
    disabled,
    media,
    setMedia,
    mediaLoading,
    setMediaLoading,
    mediaError,
    setMediaError,
    newMediaUrl,
    setNewMediaUrl,
    addingMedia,
    setAddingMedia,
  } = props

  async function loadMedia() {
    setMediaLoading(true)
    setMediaError(null)
    try {
      const res = await apiFetch(`/admin/catalog/items/${itemId}/media`)
      if (!res.ok) {
        const js = await res.json().catch(() => null)
        throw new Error(extractErrorMessage(js, `HTTP ${res.status}`))
      }
      const js = (await res.json()) as CatalogMediaOut[]
      setMedia(js)
    } catch (e) {
      setMediaError((e as Error).message || 'Erro ao carregar mídia')
    } finally {
      setMediaLoading(false)
    }
  }

  async function onAddMedia() {
    const url = (newMediaUrl || '').trim()
    if (!url) return
    setAddingMedia(true)
    setMediaError(null)
    try {
      const res = await apiFetch(`/admin/catalog/items/${itemId}/media`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: 'image', url }),
      })
      if (!res.ok) {
        const js = await res.json().catch(() => null)
        throw new Error(extractErrorMessage(js, `HTTP ${res.status}`))
      }
      setNewMediaUrl('')
      await loadMedia()
    } catch (e) {
      setMediaError((e as Error).message || 'Erro ao adicionar mídia')
    } finally {
      setAddingMedia(false)
    }
  }

  async function onDeleteMedia(mediaId: number) {
    setMediaError(null)
    try {
      const res = await apiFetch(`/admin/catalog/media/${mediaId}`, { method: 'DELETE' })
      if (!res.ok) {
        const js = await res.json().catch(() => null)
        throw new Error(extractErrorMessage(js, `HTTP ${res.status}`))
      }
      await loadMedia()
    } catch (e) {
      setMediaError((e as Error).message || 'Erro ao remover mídia')
    }
  }

  async function onReorderMedia(mediaIds: number[]) {
    setMediaError(null)
    try {
      const res = await apiFetch(`/admin/catalog/items/${itemId}/media/reorder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ media_ids: mediaIds }),
      })
      if (!res.ok) {
        const js = await res.json().catch(() => null)
        throw new Error(extractErrorMessage(js, `HTTP ${res.status}`))
      }
      await loadMedia()
    } catch (e) {
      setMediaError((e as Error).message || 'Erro ao reordenar mídia')
    }
  }

  useEffect(() => {
    void loadMedia()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [itemId])

  return (
    <div className="space-y-2">
      <div className="text-sm font-semibold text-slate-700">Mídia</div>
      {mediaError && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">{mediaError}</div>
      )}
      {mediaLoading ? (
        <div className="text-sm text-slate-500">Carregando mídia...</div>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <input
              className="input"
              value={newMediaUrl}
              onChange={e => setNewMediaUrl(e.target.value)}
              placeholder="https://..."
              disabled={addingMedia || disabled}
            />
            <button
              type="button"
              className="btn btn-secondary"
              disabled={addingMedia || disabled || !newMediaUrl.trim()}
              onClick={() => void onAddMedia()}
            >
              {addingMedia ? 'Adicionando...' : 'Adicionar'}
            </button>
          </div>

          <div className="space-y-2">
            {media.map((m, idx) => (
              <div key={m.id} className="flex items-center gap-2 bg-white border border-slate-200 rounded-lg p-2">
                <div className="w-12 h-12 bg-slate-100 rounded overflow-hidden flex items-center justify-center">
                  <img src={m.url} alt="" className="w-full h-full object-cover" />
                </div>
                <div className="flex-1">
                  <div className="text-xs text-slate-500">{m.kind}</div>
                  <div className="text-xs font-mono break-all">{m.url}</div>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={idx === 0 || disabled}
                    onClick={() => {
                      if (idx <= 0) return
                      const ids = media.map(x => x.id)
                      const a = ids[idx - 1]
                      const b = ids[idx]
                      if (a == null || b == null) return
                      ids[idx - 1] = b
                      ids[idx] = a
                      void onReorderMedia(ids)
                    }}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={idx === media.length - 1 || disabled}
                    onClick={() => {
                      if (idx >= media.length - 1) return
                      const ids = media.map(x => x.id)
                      const a = ids[idx]
                      const b = ids[idx + 1]
                      if (a == null || b == null) return
                      ids[idx] = b
                      ids[idx + 1] = a
                      void onReorderMedia(ids)
                    }}
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    disabled={disabled}
                    onClick={() => void onDeleteMedia(m.id)}
                  >
                    Remover
                  </button>
                </div>
              </div>
            ))}
            {media.length === 0 && (
              <div className="text-sm text-slate-500">Nenhuma mídia cadastrada.</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
