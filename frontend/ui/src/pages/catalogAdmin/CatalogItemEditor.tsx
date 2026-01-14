import React from 'react'
import AttributeField from './AttributeField'
import CatalogMediaEditor from './CatalogMediaEditor'
import type { CatalogFieldDefinition, CatalogMediaOut } from './types'

type EditItemState = {
  id: number
  title: string
  description?: string | null
  is_active: boolean
  attributes: Record<string, unknown>
}

type Props = {
  editingItem: EditItemState
  setEditingItem: React.Dispatch<React.SetStateAction<EditItemState | null>>
  savingEdit: boolean
  onSaveEdit: (e: React.FormEvent) => void

  selectedFields: CatalogFieldDefinition[]
  updateEditAttr: (key: string, value: unknown) => void

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

export default function CatalogItemEditor(props: Props) {
  const {
    editingItem,
    setEditingItem,
    savingEdit,
    onSaveEdit,
    selectedFields,
    updateEditAttr,
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

  return (
    <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-slate-700">Editando item #{editingItem.id}</div>
        <button className="btn btn-secondary btn-sm" onClick={() => setEditingItem(null)} disabled={savingEdit}>Fechar</button>
      </div>

      <form onSubmit={onSaveEdit} className="space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Título</label>
            <input className="input" value={editingItem.title} onChange={e => setEditingItem({ ...editingItem, title: e.target.value })} required disabled={savingEdit} />
          </div>
          <div className="flex items-center gap-2">
            <input id="edit_active" type="checkbox" checked={!!editingItem.is_active} onChange={e => setEditingItem({ ...editingItem, is_active: e.target.checked })} disabled={savingEdit} />
            <label htmlFor="edit_active" className="text-sm text-slate-700">Ativo</label>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">Descrição</label>
          <textarea className="input" value={editingItem.description || ''} onChange={e => setEditingItem({ ...editingItem, description: e.target.value })} disabled={savingEdit} />
        </div>

        <div className="space-y-2">
          <div className="text-sm font-semibold text-slate-700">Atributos</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {selectedFields.map((f) => (
              <AttributeField
                key={f.key}
                field={f}
                value={editingItem.attributes[f.key]}
                disabled={savingEdit}
                onChange={(v) => updateEditAttr(f.key, v)}
              />
            ))}
          </div>
        </div>

        <CatalogMediaEditor
          itemId={editingItem.id}
          disabled={savingEdit}
          media={media}
          setMedia={setMedia}
          mediaLoading={mediaLoading}
          setMediaLoading={setMediaLoading}
          mediaError={mediaError}
          setMediaError={setMediaError}
          newMediaUrl={newMediaUrl}
          setNewMediaUrl={setNewMediaUrl}
          addingMedia={addingMedia}
          setAddingMedia={setAddingMedia}
        />

        <div className="flex items-center gap-2">
          <button className="btn btn-primary" disabled={savingEdit}>{savingEdit ? 'Salvando...' : 'Salvar alterações'}</button>
          <button type="button" className="btn btn-secondary" onClick={() => setEditingItem(null)} disabled={savingEdit}>Cancelar</button>
        </div>
      </form>
    </div>
  )
}
