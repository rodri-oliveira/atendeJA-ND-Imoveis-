import React from 'react'
import { CATALOG_FIELD_TYPES, CatalogFieldDefinition, CatalogFieldType } from './types'

type CatalogItemType = {
  id: number
  tenant_id: number
  key: string
  name: string
  schema: { fields?: CatalogFieldDefinition[] }
  is_active: boolean
}

type EditItemTypeState = {
  id: number
  key: string
  name: string
  is_active: boolean
  fields: CatalogFieldDefinition[]
}

type Props = {
  types: CatalogItemType[]

  editingType: EditItemTypeState | null
  setEditingType: React.Dispatch<React.SetStateAction<EditItemTypeState | null>>
  savingType: boolean
  onSaveType: (e: React.FormEvent) => void
  updateEditTypeField: (idx: number, patch: Partial<CatalogFieldDefinition>) => void
  removeEditTypeField: (idx: number) => void

  creatingType: boolean
  typeKey: string
  setTypeKey: (v: string) => void
  typeName: string
  setTypeName: (v: string) => void
  typeIsActive: boolean
  setTypeIsActive: (v: boolean) => void
  fields: CatalogFieldDefinition[]
  setFields: (updater: (prev: CatalogFieldDefinition[]) => CatalogFieldDefinition[]) => void
  updateField: (idx: number, patch: Partial<CatalogFieldDefinition>) => void
  removeField: (idx: number) => void
  onCreateType: (e: React.FormEvent) => void
}


export default function CatalogItemTypesSection(props: Props) {
  const {
    types,
    editingType,
    setEditingType,
    savingType,
    onSaveType,
    updateEditTypeField,
    removeEditTypeField,
    creatingType,
    typeKey,
    setTypeKey,
    typeName,
    setTypeName,
    typeIsActive,
    setTypeIsActive,
    fields,
    setFields,
    updateField,
    removeField,
    onCreateType,
  } = props

  return (
    <div className="card space-y-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-bold text-slate-800">Item Types</h2>
          <p className="text-xs text-slate-500">Defina o schema (fields) por tenant.</p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="table min-w-full text-sm">
          <thead>
            <tr className="text-left text-slate-600">
              <th className="py-2 pr-3">Key</th>
              <th className="py-2 pr-3">Nome</th>
              <th className="py-2 pr-3">Ativo</th>
              <th className="py-2 pr-3">Fields</th>
              <th className="py-2 pr-3">Ações</th>
            </tr>
          </thead>
          <tbody>
            {types.map(t => (
              <tr key={t.id} className="table-row">
                <td className="py-2 pr-3 font-mono text-xs">{t.key}</td>
                <td className="py-2 pr-3">{t.name}</td>
                <td className="py-2 pr-3">{t.is_active ? 'Sim' : 'Não'}</td>
                <td className="py-2 pr-3 text-xs text-slate-600">{(t.schema?.fields || []).length}</td>
                <td className="py-2 pr-3">
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => setEditingType({
                      id: t.id,
                      key: t.key,
                      name: t.name,
                      is_active: t.is_active,
                      fields: ((t.schema?.fields || []) as CatalogFieldDefinition[]).map(f => ({
                        key: f.key,
                        label: f.label,
                        placeholder: f.placeholder,
                        type: (f.type as string) === 'enum' ? 'select' : f.type,
                        required: !!f.required,
                        options: Array.isArray(f.options) ? f.options.map(opt => typeof opt === 'string' ? { value: opt, label: opt } : opt) : null,
                      })),
                    })}
                  >
                    Editar
                  </button>
                </td>
              </tr>
            ))}
            {types.length === 0 && (
              <tr>
                <td className="py-3 text-sm text-slate-500" colSpan={5}>Nenhum item type ainda.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {editingType && (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-slate-700">Editando Item Type</div>
              <div className="text-xs text-slate-500 font-mono">{editingType.key}</div>
            </div>
            <button className="btn btn-secondary btn-sm" onClick={() => setEditingType(null)} disabled={savingType}>Fechar</button>
          </div>

          <form onSubmit={onSaveType} className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">Nome</label>
                <input className="input" value={editingType.name} onChange={e => setEditingType({ ...editingType, name: e.target.value })} disabled={savingType} />
              </div>
              <div className="flex items-center gap-2">
                <input id="edit_type_active" type="checkbox" checked={!!editingType.is_active} onChange={e => setEditingType({ ...editingType, is_active: e.target.checked })} disabled={savingType} />
                <label htmlFor="edit_type_active" className="text-sm text-slate-700">Ativo</label>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium text-slate-700">Fields</div>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={savingType}
                  onClick={() => setEditingType(prev => prev ? ({ ...prev, fields: [...prev.fields, { key: '', label: '', type: 'text', required: false, options: null }] }) : prev)}
                >
                  + Field
                </button>
              </div>

              <div className="space-y-2">
                {(editingType.fields || []).map((f, idx) => (
                  <div key={idx} className="grid grid-cols-1 md:grid-cols-10 gap-2 items-end bg-white border border-slate-200 rounded-lg p-3">
                    <div className="md:col-span-2">
                      <label className="block text-xs font-semibold text-slate-600">Key</label>
                      <input className="input" value={f.key} onChange={e => updateEditTypeField(idx, { key: e.target.value })} disabled={savingType} />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-xs font-semibold text-slate-600">Label</label>
                      <input className="input" value={f.label} onChange={e => updateEditTypeField(idx, { label: e.target.value })} disabled={savingType} />
                    </div>
                    <div className="md:col-span-1">
                      <label className="block text-xs font-semibold text-slate-600">Placeholder</label>
                      <input className="input" value={f.placeholder || ''} onChange={e => updateEditTypeField(idx, { placeholder: e.target.value })} disabled={savingType} />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-xs font-semibold text-slate-600">Tipo</label>
                      <select
                        className="select"
                        value={f.type}
                        onChange={e => updateEditTypeField(idx, { type: e.target.value as CatalogFieldType })}
                        disabled={savingType}
                      >
                        {CATALOG_FIELD_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                      </select>
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-xs font-semibold text-slate-600">Opções (select)</label>
                      <textarea
                        className="input"
                        value={(f.options || []).map(opt => `${opt.value}:${opt.label}`).join('\n')}
                        onChange={e => {
                          const options = (e.target.value || '').split('\n').map(line => {
                            const [value, ...labelParts] = line.split(':');
                            const label = labelParts.join(':');
                            return { value: (value || '').trim(), label: (label || '').trim() || (value || '').trim() };
                          }).filter(opt => opt.value);
                          updateEditTypeField(idx, { options });
                        }}
                        disabled={savingType || f.type !== 'select'}
                        placeholder="valor:Label (um por linha)"
                        rows={2}
                      />
                    </div>
                    <div className="md:col-span-1 flex items-center justify-between gap-2">
                      <label className="text-xs text-slate-700 flex items-center gap-2">
                        <input type="checkbox" checked={!!f.required} onChange={e => updateEditTypeField(idx, { required: e.target.checked })} disabled={savingType} />
                        req
                      </label>
                      <button type="button" className="btn btn-secondary btn-sm" onClick={() => removeEditTypeField(idx)} disabled={savingType || (editingType.fields || []).length <= 1}>X</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button className="btn btn-primary" disabled={savingType}>{savingType ? 'Salvando...' : 'Salvar Item Type'}</button>
              <button type="button" className="btn btn-secondary" onClick={() => setEditingType(null)} disabled={savingType}>Cancelar</button>
            </div>
          </form>
        </div>
      )}

      <div className="border-t border-slate-200 pt-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Criar Item Type</h3>
        <form onSubmit={onCreateType} className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Key</label>
              <input className="input" value={typeKey} onChange={e => setTypeKey(e.target.value)} placeholder="ex: vehicle" required disabled={creatingType} />
              <div className="text-xs text-slate-500 mt-1">Normaliza para snake_case.</div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Nome</label>
              <input className="input" value={typeName} onChange={e => setTypeName(e.target.value)} placeholder="ex: Veículos" disabled={creatingType} />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <input id="type_active" type="checkbox" checked={typeIsActive} onChange={e => setTypeIsActive(e.target.checked)} disabled={creatingType} />
            <label htmlFor="type_active" className="text-sm text-slate-700">Ativo</label>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="text-sm font-medium text-slate-700">Fields</div>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={creatingType}
                onClick={() => setFields(prev => [...prev, { key: '', label: '', type: 'text', required: false, options: null }])}
              >
                + Field
              </button>
            </div>

            <div className="space-y-2">
              {fields.map((f, idx) => (
                <div key={idx} className="grid grid-cols-1 md:grid-cols-10 gap-2 items-end bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <div className="md:col-span-2">
                    <label className="block text-xs font-semibold text-slate-600">Key</label>
                    <input className="input" value={f.key} onChange={e => updateField(idx, { key: e.target.value })} disabled={creatingType} />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-xs font-semibold text-slate-600">Label</label>
                    <input className="input" value={f.label} onChange={e => updateField(idx, { label: e.target.value })} disabled={creatingType} />
                  </div>
                  <div className="md:col-span-1">
                    <label className="block text-xs font-semibold text-slate-600">Placeholder</label>
                    <input className="input" value={f.placeholder || ''} onChange={e => updateField(idx, { placeholder: e.target.value })} disabled={creatingType} />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-xs font-semibold text-slate-600">Tipo</label>
                    <select
                      className="select"
                      value={f.type}
                      onChange={e => updateField(idx, { type: e.target.value as CatalogFieldType })}
                      disabled={creatingType}
                    >
                      {CATALOG_FIELD_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-xs font-semibold text-slate-600">Opções (select)</label>
                    <textarea
                      className="input"
                      value={(f.options || []).map(opt => `${opt.value}:${opt.label}`).join('\n')}
                      onChange={e => {
                        const options = (e.target.value || '').split('\n').map(line => {
                          const [value, ...labelParts] = line.split(':');
                          const label = labelParts.join(':');
                          return { value: (value || '').trim(), label: (label || '').trim() || (value || '').trim() };
                        }).filter(opt => opt.value);
                        updateField(idx, { options });
                      }}
                      disabled={creatingType || f.type !== 'select'}
                      placeholder="valor:Label (um por linha)"
                      rows={2}
                    />
                  </div>
                  <div className="md:col-span-1 flex items-center justify-between gap-2">
                    <label className="text-xs text-slate-700 flex items-center gap-2">
                      <input type="checkbox" checked={!!f.required} onChange={e => updateField(idx, { required: e.target.checked })} disabled={creatingType} />
                      req
                    </label>
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => removeField(idx)} disabled={creatingType || fields.length <= 1}>X</button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button className="btn btn-primary" disabled={creatingType}>{creatingType ? 'Criando...' : 'Criar Item Type'}</button>
          </div>
        </form>
      </div>
    </div>
  )
}
