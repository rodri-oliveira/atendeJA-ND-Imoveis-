import React from 'react'
import AttributeField from './AttributeField'
import type { CatalogFieldDefinition } from './types'

type CatalogItemOut = {
  id: number
  title: string
  description?: string | null
  attributes: Record<string, unknown>
  is_active: boolean
}

type EditItemState = {
  id: number
  title: string
  description?: string | null
  is_active: boolean
  attributes: Record<string, unknown>
}

type Props = {
  selectedTypeKey: string
  setSelectedTypeKey: (v: string) => void
  types: { id: number; key: string; name: string; is_active: boolean }[]

  itemTitle: string
  setItemTitle: (v: string) => void
  itemDescription: string
  setItemDescription: (v: string) => void
  itemIsActive: boolean
  setItemIsActive: (v: boolean) => void
  itemAttributes: Record<string, unknown>
  updateAttr: (key: string, value: unknown) => void
  creatingItem: boolean
  onCreateItem: (e: React.FormEvent) => void
  selectedFields: CatalogFieldDefinition[]

  lastCreatedItem: CatalogItemOut | null

  items: CatalogItemOut[]
  itemsLoading: boolean
  itemsError: string | null
  loadItems: (typeKey: string) => void

  setEditingItem: React.Dispatch<React.SetStateAction<EditItemState | null>>
  onToggleItemActive: (itemId: number, nextActive: boolean) => void
}

export default function CatalogItemsSection(props: Props) {
  const {
    selectedTypeKey,
    setSelectedTypeKey,
    types,
    itemTitle,
    setItemTitle,
    itemDescription,
    setItemDescription,
    itemIsActive,
    setItemIsActive,
    itemAttributes,
    updateAttr,
    creatingItem,
    onCreateItem,
    selectedFields,
    lastCreatedItem,
    items,
    itemsLoading,
    itemsError,
    loadItems,
    setEditingItem,
    onToggleItemActive,
  } = props

  return (
    <div className="card space-y-4">
      <div>
        <h2 className="text-lg font-bold text-slate-800">Criar Item</h2>
        <p className="text-xs text-slate-500">Formulário gerado pelo schema do Item Type.</p>
      </div>

      <form onSubmit={onCreateItem} className="space-y-3">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">Item Type</label>
          <select className="select" value={selectedTypeKey} onChange={e => { setSelectedTypeKey(e.target.value); }}>
            {types.filter(t => t.is_active).map(t => (
              <option key={t.id} value={t.key}>{t.name} ({t.key})</option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Título</label>
            <input className="input" value={itemTitle} onChange={e => setItemTitle(e.target.value)} required disabled={creatingItem} />
          </div>
          <div className="flex items-center gap-2">
            <input id="item_active" type="checkbox" checked={itemIsActive} onChange={e => setItemIsActive(e.target.checked)} disabled={creatingItem} />
            <label htmlFor="item_active" className="text-sm text-slate-700">Ativo</label>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">Descrição</label>
          <textarea className="input" value={itemDescription} onChange={e => setItemDescription(e.target.value)} disabled={creatingItem} />
        </div>

        <div className="space-y-2">
          <div className="text-sm font-semibold text-slate-700">Atributos</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {selectedFields.map((f) => (
              <AttributeField
                key={f.key}
                field={f}
                value={itemAttributes[f.key]}
                disabled={creatingItem}
                onChange={(v) => updateAttr(f.key, v)}
              />
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button className="btn btn-primary" disabled={creatingItem || !selectedTypeKey}>{creatingItem ? 'Criando...' : 'Criar Item'}</button>
        </div>

        {lastCreatedItem && (
          <div className="text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-3">
            Item criado: <strong>#{lastCreatedItem.id}</strong> — {lastCreatedItem.title}
          </div>
        )}
      </form>

      <div className="border-t border-slate-200 pt-4 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-700">Itens do tipo</h3>
            <div className="text-xs text-slate-500">{selectedTypeKey || '-'}</div>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={() => loadItems(selectedTypeKey)} disabled={itemsLoading || !selectedTypeKey}>Recarregar</button>
        </div>

        {itemsLoading && <div className="text-sm text-slate-500">Carregando itens...</div>}
        {itemsError && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">{itemsError}</div>}

        {!itemsLoading && !itemsError && (
          <div className="overflow-x-auto">
            <table className="table min-w-full text-sm">
              <thead>
                <tr className="text-left text-slate-600">
                  <th className="py-2 pr-3">ID</th>
                  <th className="py-2 pr-3">Título</th>
                  <th className="py-2 pr-3">Ativo</th>
                  <th className="py-2 pr-3">Ações</th>
                </tr>
              </thead>
              <tbody>
                {items.map(it => (
                  <tr key={it.id} className="table-row">
                    <td className="py-2 pr-3">{it.id}</td>
                    <td className="py-2 pr-3">{it.title}</td>
                    <td className="py-2 pr-3">{it.is_active ? 'Sim' : 'Não'}</td>
                    <td className="py-2 pr-3">
                      <div className="flex items-center gap-2">
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => setEditingItem({
                            id: it.id,
                            title: it.title,
                            description: it.description || null,
                            is_active: it.is_active,
                            attributes: { ...(it.attributes || {}) },
                          })}
                        >
                          Editar
                        </button>
                        <button
                          className={`btn btn-sm ${it.is_active ? 'btn-warning' : 'btn-success'}`}
                          onClick={() => onToggleItemActive(it.id, !it.is_active)}
                        >
                          {it.is_active ? 'Desativar' : 'Ativar'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr>
                    <td className="py-3 text-sm text-slate-500" colSpan={4}>Nenhum item encontrado.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
