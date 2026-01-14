import React, { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../lib/auth'
import CatalogItemEditor from './catalogAdmin/CatalogItemEditor'
import CatalogItemTypesSection from './catalogAdmin/CatalogItemTypesSection'
import CatalogItemsSection from './catalogAdmin/CatalogItemsSection'
import type { CatalogFieldDefinition, CatalogMediaOut } from './catalogAdmin/types'
import { extractErrorMessage, normalizeKey } from './catalogAdmin/utils'

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

export default function CatalogAdmin() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [types, setTypes] = useState<CatalogItemType[]>([])
  const [creatingType, setCreatingType] = useState(false)
  const [typeKey, setTypeKey] = useState('')
  const [typeName, setTypeName] = useState('')
  const [typeIsActive, setTypeIsActive] = useState(true)
  const [fields, setFields] = useState<CatalogFieldDefinition[]>([
    { key: 'price', label: 'Preço', type: 'number', required: true, options: null },
  ])

  const [editingType, setEditingType] = useState<EditItemTypeState | null>(null)
  const [savingType, setSavingType] = useState(false)

  const [selectedTypeKey, setSelectedTypeKey] = useState<string>('')
  const [itemTitle, setItemTitle] = useState('')
  const [itemDescription, setItemDescription] = useState('')
  const [itemIsActive, setItemIsActive] = useState(true)
  const [itemAttributes, setItemAttributes] = useState<Record<string, unknown>>({})
  const [creatingItem, setCreatingItem] = useState(false)
  const [lastCreatedItem, setLastCreatedItem] = useState<CatalogItemOut | null>(null)

  const [items, setItems] = useState<CatalogItemOut[]>([])
  const [itemsLoading, setItemsLoading] = useState(false)
  const [itemsError, setItemsError] = useState<string | null>(null)
  const [editingItem, setEditingItem] = useState<EditItemState | null>(null)
  const [savingEdit, setSavingEdit] = useState(false)

  const [media, setMedia] = useState<CatalogMediaOut[]>([])
  const [mediaLoading, setMediaLoading] = useState(false)
  const [mediaError, setMediaError] = useState<string | null>(null)
  const [newMediaUrl, setNewMediaUrl] = useState('')
  const [addingMedia, setAddingMedia] = useState(false)

  const selectedType = useMemo(() => types.find(t => t.key === selectedTypeKey) || null, [types, selectedTypeKey])
  const selectedFields = useMemo(() => (selectedType?.schema?.fields || []) as CatalogFieldDefinition[], [selectedType])

  async function loadItems(typeKey: string) {
    if (!typeKey) {
      setItems([])
      return
    }
    setItemsLoading(true)
    setItemsError(null)
    try {
      const res = await apiFetch(`/admin/catalog/items?item_type_key=${encodeURIComponent(typeKey)}&limit=200`)
      if (!res.ok) {
        const js = await res.json().catch(() => null)
        throw new Error(extractErrorMessage(js, `HTTP ${res.status}`))
      }
      const js = (await res.json()) as CatalogItemOut[]
      setItems(js)
    } catch (e) {
      setItemsError((e as Error).message || 'Erro ao carregar itens')
    } finally {
      setItemsLoading(false)
    }
  }

  function updateEditTypeField(idx: number, patch: Partial<CatalogFieldDefinition>) {
    setEditingType(prev => {
      if (!prev) return prev
      const next = prev.fields.map((f, i) => (i === idx ? { ...f, ...patch } : f))
      return { ...prev, fields: next }
    })
  }

  function removeEditTypeField(idx: number) {
    setEditingType(prev => {
      if (!prev) return prev
      const next = prev.fields.filter((_, i) => i !== idx)
      return { ...prev, fields: next }
    })
  }

  async function onSaveType(e: React.FormEvent) {
    e.preventDefault()
    if (!editingType) return
    setSavingType(true)
    setError(null)

    try {
      const payload = {
        name: (editingType.name || '').trim(),
        is_active: !!editingType.is_active,
        schema: {
          fields: (editingType.fields || []).map(f => ({ ...f, key: normalizeKey(f.key) })),
        },
      }

      const res = await apiFetch(`/admin/catalog/item-types/${editingType.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const js = await res.json().catch(() => null)
        throw new Error(extractErrorMessage(js, `HTTP ${res.status}`))
      }

      const editedKey = editingType.key
      setEditingType(null)
      await load()
      if (editedKey === selectedTypeKey) {
        await loadItems(selectedTypeKey)
      }
    } catch (e) {
      setError((e as Error).message || 'Erro ao salvar item type')
    } finally {
      setSavingType(false)
    }
  }

  async function onToggleItemActive(itemId: number, nextActive: boolean) {
    setItemsError(null)
    try {
      const res = await apiFetch(`/admin/catalog/items/${itemId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: nextActive }),
      })
      if (!res.ok) {
        const js = await res.json().catch(() => null)
        throw new Error(extractErrorMessage(js, `HTTP ${res.status}`))
      }
      setItems(prev => prev.map(it => (it.id === itemId ? { ...it, is_active: nextActive } : it)))
    } catch (e) {
      setItemsError((e as Error).message || 'Erro ao atualizar item')
    }
  }

  function updateEditAttr(key: string, value: unknown) {
    setEditingItem(prev => {
      if (!prev) return prev
      return { ...prev, attributes: { ...(prev.attributes || {}), [key]: value } }
    })
  }

  async function onSaveEdit(e: React.FormEvent) {
    e.preventDefault()
    if (!editingItem) return
    setSavingEdit(true)
    setError(null)

    try {
      const payload = {
        title: (editingItem.title || '').trim(),
        description: (editingItem.description || '').trim() || null,
        is_active: !!editingItem.is_active,
        attributes: editingItem.attributes,
      }

      const res = await apiFetch(`/admin/catalog/items/${editingItem.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const js = await res.json().catch(() => null)
        throw new Error(extractErrorMessage(js, `HTTP ${res.status}`))
      }

      setEditingItem(null)
      await loadItems(selectedTypeKey)
    } catch (e) {
      setError((e as Error).message || 'Erro ao salvar item')
    } finally {
      setSavingEdit(false)
    }
  }

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch('/admin/catalog/item-types?include_inactive=true')
      if (!res.ok) {
        const js = await res.json().catch(() => null)
        throw new Error(extractErrorMessage(js, `HTTP ${res.status}`))
      }
      const js = (await res.json()) as CatalogItemType[]
      setTypes(js)

      if (!selectedTypeKey && js.length > 0) {
        const first = js.find(t => t.is_active) || js[0]
        const key = first ? first.key : ''
        if (key) setSelectedTypeKey(key)
      }
    } catch (e) {
      setError((e as Error).message || 'Erro ao carregar catálogo')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    void loadItems(selectedTypeKey)
    setEditingItem(null)
    setMedia([])
    setMediaError(null)
    setNewMediaUrl('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTypeKey])

  function updateField(idx: number, patch: Partial<CatalogFieldDefinition>) {
    setFields(prev => prev.map((f, i) => (i === idx ? { ...f, ...patch } : f)))
  }

  function removeField(idx: number) {
    setFields(prev => prev.filter((_, i) => i !== idx))
  }

  function resetTypeForm() {
    setTypeKey('')
    setTypeName('')
    setTypeIsActive(true)
    setFields([{ key: 'price', label: 'Preço', type: 'number', required: true, options: null }])
  }

  async function onCreateType(e: React.FormEvent) {
    e.preventDefault()
    setCreatingType(true)
    setError(null)

    try {
      const payload = {
        key: normalizeKey(typeKey),
        name: (typeName || '').trim() || normalizeKey(typeKey),
        schema: { fields: fields.map(f => ({ ...f, key: normalizeKey(f.key) })) },
        is_active: !!typeIsActive,
      }

      const res = await apiFetch('/admin/catalog/item-types', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const js = await res.json().catch(() => null)
        throw new Error(extractErrorMessage(js, `HTTP ${res.status}`))
      }

      resetTypeForm()
      await load()
    } catch (e) {
      setError((e as Error).message || 'Erro ao criar item type')
    } finally {
      setCreatingType(false)
    }
  }

  function updateAttr(key: string, value: unknown) {
    setItemAttributes(prev => ({ ...prev, [key]: value }))
  }

  function resetItemForm() {
    setItemTitle('')
    setItemDescription('')
    setItemIsActive(true)
    setItemAttributes({})
  }

  async function onCreateItem(e: React.FormEvent) {
    e.preventDefault()
    setCreatingItem(true)
    setError(null)
    setLastCreatedItem(null)

    try {
      const payload = {
        item_type_key: selectedTypeKey,
        title: (itemTitle || '').trim(),
        description: (itemDescription || '').trim() || null,
        attributes: itemAttributes,
        is_active: !!itemIsActive,
      }

      const res = await apiFetch('/admin/catalog/items', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const js = await res.json().catch(() => null)
        throw new Error(extractErrorMessage(js, `HTTP ${res.status}`))
      }

      const js = (await res.json()) as CatalogItemOut
      setLastCreatedItem(js)
      resetItemForm()
    } catch (e) {
      setError((e as Error).message || 'Erro ao criar item')
    } finally {
      setCreatingItem(false)
    }
  }

  return (
    <section className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Admin do Catálogo</h1>
          <p className="text-sm text-slate-500">Item Types (schema) e criação manual de itens.</p>
        </div>
        <button onClick={load} className="btn btn-secondary" disabled={loading}>Recarregar</button>
      </header>

      {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">{error}</div>}
      {loading && <div className="text-sm text-slate-500">Carregando...</div>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <CatalogItemTypesSection
          types={types}
          editingType={editingType}
          setEditingType={setEditingType}
          savingType={savingType}
          onSaveType={onSaveType}
          updateEditTypeField={updateEditTypeField}
          removeEditTypeField={removeEditTypeField}
          creatingType={creatingType}
          typeKey={typeKey}
          setTypeKey={setTypeKey}
          typeName={typeName}
          setTypeName={setTypeName}
          typeIsActive={typeIsActive}
          setTypeIsActive={setTypeIsActive}
          fields={fields}
          setFields={setFields}
          updateField={updateField}
          removeField={removeField}
          onCreateType={onCreateType}
        />

        <div className="space-y-4">
          <CatalogItemsSection
            selectedTypeKey={selectedTypeKey}
            setSelectedTypeKey={(v) => { setSelectedTypeKey(v); setItemAttributes({}); }}
            types={types}
            itemTitle={itemTitle}
            setItemTitle={setItemTitle}
            itemDescription={itemDescription}
            setItemDescription={setItemDescription}
            itemIsActive={itemIsActive}
            setItemIsActive={setItemIsActive}
            itemAttributes={itemAttributes}
            updateAttr={updateAttr}
            creatingItem={creatingItem}
            onCreateItem={onCreateItem}
            selectedFields={selectedFields}
            lastCreatedItem={lastCreatedItem}
            items={items}
            itemsLoading={itemsLoading}
            itemsError={itemsError}
            loadItems={(k) => void loadItems(k)}
            setEditingItem={setEditingItem}
            onToggleItemActive={(id, next) => void onToggleItemActive(id, next)}
          />

          {editingItem && (
            <CatalogItemEditor
              editingItem={editingItem}
              setEditingItem={setEditingItem}
              savingEdit={savingEdit}
              onSaveEdit={onSaveEdit}
              selectedFields={selectedFields}
              updateEditAttr={updateEditAttr}
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
          )}
        </div>
      </div>
    </section>
  )
}
