import React from 'react'
import type { CatalogFieldDefinition } from './types'

type Props = {
  field: CatalogFieldDefinition
  value: unknown
  disabled: boolean
  onChange: (value: unknown) => void
}

export default function AttributeField({ field: f, value, disabled, onChange }: Props) {
  const k = f.key
  const label = `${f.label}${f.required ? ' *' : ''}`

  if (f.type === 'boolean') {
    return (
      <label key={k} className="flex items-center gap-2 text-sm text-slate-700">
        <input type="checkbox" checked={!!value} onChange={e => onChange(e.target.checked)} disabled={disabled} />
        {label}
      </label>
    )
  }

  if (f.type === 'enum') {
    return (
      <div key={k}>
        <label className="block text-sm font-medium text-slate-700 mb-2">{label}</label>
        <select
          className="select"
          value={typeof value === 'string' ? value : ''}
          onChange={e => onChange(e.target.value)}
          disabled={disabled}
          required={!!f.required}
        >
          <option value="">Selecione</option>
          {(f.options || []).map(opt => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      </div>
    )
  }

  if (f.type === 'number') {
    return (
      <div key={k}>
        <label className="block text-sm font-medium text-slate-700 mb-2">{label}</label>
        <input
          className="input"
          type="number"
          value={typeof value === 'number' ? String(value) : ''}
          onChange={e => onChange(e.target.value === '' ? undefined : Number(e.target.value))}
          disabled={disabled}
          required={!!f.required}
        />
      </div>
    )
  }

  return (
    <div key={k}>
      <label className="block text-sm font-medium text-slate-700 mb-2">{label}</label>
      <input
        className="input"
        value={typeof value === 'string' ? value : ''}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
        required={!!f.required}
      />
    </div>
  )
}
