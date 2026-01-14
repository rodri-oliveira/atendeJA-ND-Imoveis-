export const CATALOG_FIELD_TYPES = ['text', 'textarea', 'number', 'currency', 'boolean', 'select'] as const
export type CatalogFieldType = (typeof CATALOG_FIELD_TYPES)[number]

export type CatalogFieldDefinition = {
  key: string
  label: string
  placeholder?: string | null
  type: CatalogFieldType
  required: boolean
  options?: Array<{ value: string; label: string }> | null
}

export type CatalogMediaOut = {
  id: number
  item_id: number
  kind: string
  url: string
  sort_order: number
}
