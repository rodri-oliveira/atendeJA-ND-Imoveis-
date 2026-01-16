import React, { useEffect, useMemo, useState } from 'react'
import { apiFetch, isAuthenticated } from '../lib/auth'
import { useNavigate } from 'react-router-dom'
import { useTenant } from '../contexts/TenantContext'

type Tenant = {
  id: number
  name: string
  timezone: string
  is_active: boolean
}

type WhatsAppAccount = {
  id: number
  tenant_id: number
  phone_number_id: string
  waba_id?: string | null
  is_active: boolean
}

type InviteAdminOut = {
  token: string
  email: string
  tenant_id: number
  role: string
}

type AssignUserOut = {
  user_id: number
  email: string
  tenant_id: number
}

type OnboardByUrlOut = {
  tenant_id: number
  tenant_name: string
  chatbot_domain: string
  flow_id: number
  published: boolean
  published_version?: number | null
  whatsapp_account_id?: number | null
  invite_token?: string | null
  invite_email?: string | null
}

type ChatbotTemplate = {
  domain: string
  template: string
}

type ChatbotDomain = string

type TenantDomainsOut = {
  tenant_id: number
  tenant_name?: string | null
  active_domain: string
  enabled_domains: string[]
  by_domain: Array<{
    domain: string
    has_published_flow: boolean
    has_lead_kanban: boolean
    has_lead_summary: boolean
  }>
}

type OnboardingRunOut = {
  id: number
  idempotency_key: string
  status: string
  tenant_id: number | null
  request_json: Record<string, unknown>
  response_json: Record<string, unknown> | null
  error_code: string | null
  created_at: string
  updated_at: string
}

export default function SuperTenants() {
  const authed = isAuthenticated()
  const navigate = useNavigate()
  const { tenantId, setTenantId } = useTenant()

  const [tenants, setTenants] = useState<Tenant[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [timezone, setTimezone] = useState('America/Sao_Paulo')
  const [creating, setCreating] = useState(false)

  const [selectedTenantId, setSelectedTenantId] = useState<number | null>(() => (tenantId ? parseInt(tenantId, 10) : null))
  const selectedTenant = useMemo(
    () => tenants.find(t => t.id === selectedTenantId) || null,
    [tenants, selectedTenantId]
  )

  const [supportedDomains, setSupportedDomains] = useState<string[]>(['real_estate'])
  const [selectedTenantDomain, setSelectedTenantDomain] = useState<string>('real_estate')
  const [selectedTenantEnabledDomains, setSelectedTenantEnabledDomains] = useState<string[]>(['real_estate'])
  const [selectedTenantDomainStatus, setSelectedTenantDomainStatus] = useState<TenantDomainsOut['by_domain']>([])
  const [domainLoading, setDomainLoading] = useState(false)
  const [domainError, setDomainError] = useState<string | null>(null)

  async function reloadSelectedTenantDomains(nextSelectedTenantId?: number | null) {
    const tid = typeof nextSelectedTenantId === 'number' ? nextSelectedTenantId : selectedTenantId
    if (!tid) return
    setDomainLoading(true)
    setDomainError(null)
    try {
      const res = await apiFetch('/api/ui/tenant/domains', {
        headers: {
          'X-Tenant-Id': String(tid),
        },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const js = (await res.json()) as TenantDomainsOut
      const active = (js?.active_domain || '').trim() || 'real_estate'
      const enabled = Array.isArray(js?.enabled_domains) ? js.enabled_domains.map((d) => String(d || '').trim()).filter(Boolean) : []
      const statusList = Array.isArray(js?.by_domain) ? js.by_domain : []

      setSelectedTenantDomain(active)
      setSelectedTenantEnabledDomains(enabled.length ? enabled : [active])
      setSelectedTenantDomainStatus(statusList)
    } catch (e) {
      setDomainError((e as Error)?.message || 'falha ao carregar domínio')
    } finally {
      setDomainLoading(false)
    }
  }

  useEffect(() => {
    let alive = true
    async function loadSupportedDomains() {
      try {
        const res = await apiFetch('/api/ui/domains', { cache: 'no-store' })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const js = (await res.json()) as { domains?: string[] }
        const list = Array.isArray(js?.domains) ? js.domains.map((d) => String(d || '').trim()).filter(Boolean) : []
        if (alive) setSupportedDomains(list.length ? list : ['real_estate'])
      } catch {
        if (alive) setSupportedDomains(['real_estate'])
      }
    }
    loadSupportedDomains()
    return () => { alive = false }
  }, [])

  useEffect(() => {
    let alive = true
    async function loadDomainForSelectedTenant() {
      if (!selectedTenantId) return
      setDomainLoading(true)
      setDomainError(null)
      try {
        const res = await apiFetch('/api/ui/tenant/domains', {
          headers: {
            'X-Tenant-Id': String(selectedTenantId),
          },
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const js = (await res.json()) as TenantDomainsOut
        const active = (js?.active_domain || '').trim() || 'real_estate'
        const enabled = Array.isArray(js?.enabled_domains) ? js.enabled_domains.map((d) => String(d || '').trim()).filter(Boolean) : []
        const statusList = Array.isArray(js?.by_domain) ? js.by_domain : []

        if (alive) {
          setSelectedTenantDomain(active)
          setSelectedTenantEnabledDomains(enabled.length ? enabled : [active])
          setSelectedTenantDomainStatus(statusList)
        }
      } catch (e) {
        if (alive) setDomainError((e as Error)?.message || 'falha ao carregar domínio')
      } finally {
        if (alive) setDomainLoading(false)
      }
    }
    loadDomainForSelectedTenant()
    return () => {
      alive = false
    }
  }, [selectedTenantId])

  async function applyDefaultTemplateForDomain(domain: string) {
    if (!selectedTenantId) return
    const d = String(domain || '').trim()
    if (!d) return
    setDomainLoading(true)
    setDomainError(null)
    try {
      const res = await apiFetch(`/super/onboarding/steps/tenants/${selectedTenantId}/apply-flow-template`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          chatbot_domain: d,
          template: 'default',
          flow_name: 'default',
          overwrite_flow: true,
          publish_flow: true,
        }),
      })
      if (!res.ok) {
        const msg = await res.text().catch(() => '')
        throw new Error(msg || `HTTP ${res.status}`)
      }
      await reloadSelectedTenantDomains(selectedTenantId)
    } catch (e) {
      setDomainError((e as Error)?.message || 'falha ao aplicar template')
    } finally {
      setDomainLoading(false)
    }
  }

  async function saveSelectedTenantDomain() {
    if (!selectedTenantId) return
    setDomainLoading(true)
    setDomainError(null)
    try {
      const res = await apiFetch('/api/ui/tenant/active-domain', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-Id': String(selectedTenantId),
        },
        body: JSON.stringify({ active_domain: selectedTenantDomain }),
      })
      if (!res.ok) {
        const msg = await res.text().catch(() => '')
        throw new Error(msg || `HTTP ${res.status}`)
      }
      const js = (await res.json()) as TenantDomainsOut
      const active = (js?.active_domain || '').trim() || selectedTenantDomain
      const enabled = Array.isArray(js?.enabled_domains) ? js.enabled_domains.map((d) => String(d || '').trim()).filter(Boolean) : []
      const statusList = Array.isArray(js?.by_domain) ? js.by_domain : []
      setSelectedTenantDomain(active)
      setSelectedTenantEnabledDomains(enabled.length ? enabled : [active])
      setSelectedTenantDomainStatus(statusList)
    } catch (e) {
      setDomainError((e as Error)?.message || 'falha ao salvar domínio')
    } finally {
      setDomainLoading(false)
    }
  }

  async function saveSelectedTenantEnabledDomains() {
    if (!selectedTenantId) return
    setDomainLoading(true)
    setDomainError(null)
    try {
      const res = await apiFetch('/api/ui/tenant/enabled-domains', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-Id': String(selectedTenantId),
        },
        body: JSON.stringify({ enabled_domains: selectedTenantEnabledDomains }),
      })
      if (!res.ok) {
        const msg = await res.text().catch(() => '')
        throw new Error(msg || `HTTP ${res.status}`)
      }
      const js = (await res.json()) as TenantDomainsOut
      const active = (js?.active_domain || '').trim() || selectedTenantDomain
      const enabled = Array.isArray(js?.enabled_domains) ? js.enabled_domains.map((d) => String(d || '').trim()).filter(Boolean) : []
      const statusList = Array.isArray(js?.by_domain) ? js.by_domain : []
      setSelectedTenantDomain(active)
      setSelectedTenantEnabledDomains(enabled.length ? enabled : [active])
      setSelectedTenantDomainStatus(statusList)
    } catch (e) {
      setDomainError((e as Error)?.message || 'falha ao salvar domínios habilitados')
    } finally {
      setDomainLoading(false)
    }
  }

  const [wizardTenantId, setWizardTenantId] = useState<number | null>(null)
  const [wizardWhatsAppAccountId, setWizardWhatsAppAccountId] = useState<number | null>(null)
  const [wizardInviteEmail, setWizardInviteEmail] = useState<string | null>(null)
  const [wizardInviteToken, setWizardInviteToken] = useState<string | null>(null)

  function onOpenFlows() {
    if (!selectedTenant) return
    setTenantId(String(selectedTenant.id))
    try {
      const key = localStorage.getItem('ui_super_admin_key')
      if (!key) {
        window.alert(`Abrindo /flows. Para editar flows deste tenant, faça login como admin do tenant "${selectedTenant.name}" (#${selectedTenant.id}).`)
      }
    } catch {
      window.alert(`Abrindo /flows. Para editar flows deste tenant, faça login como admin do tenant "${selectedTenant.name}" (#${selectedTenant.id}).`)
    }
    navigate('/flows')
  }

  async function onWizardCreateWhatsAppAccount(e: React.FormEvent) {
    e.preventDefault()
    if (!wizardTenantId) return
    setError(null)
    try {
      const res = await apiFetch(`/super/tenants/${wizardTenantId}/whatsapp-accounts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone_number_id: onboardPhoneNumberId,
          token: onboardToken || undefined,
          waba_id: onboardWabaId || undefined,
          is_active: true,
        }),
      })
      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try {
          const js = await res.json()
          msg = js?.detail || js?.error?.code || js?.message || msg
        } catch {
          // ignore
        }
        throw new Error(msg)
      }
      const js = (await res.json()) as WhatsAppAccount
      setWizardWhatsAppAccountId(js.id)
      await loadWhatsAppAccounts(wizardTenantId)
      setOnboardPhoneNumberId('')
      setOnboardWabaId('')
      setOnboardToken('')
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao criar whatsapp account (wizard)')
    }
  }

  async function onWizardInviteAdmin(e: React.FormEvent) {
    e.preventDefault()
    if (!wizardTenantId) return
    setError(null)
    try {
      const res = await apiFetch(`/super/tenants/${wizardTenantId}/invite-admin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: onboardInviteEmail, expires_hours: onboardInviteExpiresHours }),
      })
      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try {
          const js = await res.json()
          msg = js?.detail || js?.error?.code || js?.message || msg
        } catch {
          // ignore
        }
        throw new Error(msg)
      }
      const js = (await res.json()) as InviteAdminOut
      setWizardInviteEmail(js.email)
      setWizardInviteToken(js.token)
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao convidar admin (wizard)')
    }
  }


  async function setTenantActive(tid: number, next: boolean) {
    setError(null)
    try {
      const res = await apiFetch(`/super/tenants/${tid}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: next }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await loadTenants()
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao atualizar tenant')
    }

  }

  async function onAssignUser(e: React.FormEvent) {
    e.preventDefault()
    if (selectedTenantId == null) return
    setAssigning(true)
    setError(null)
    try {
      const res = await apiFetch(`/super/tenants/${selectedTenantId}/assign-user`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: assignEmail }),
      })
      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try {
          const js = await res.json()
          msg = js?.detail || js?.message || msg
        } catch {
          // ignore
        }
        throw new Error(msg)
      }
      const js = (await res.json()) as AssignUserOut
      setLastAssign(js)
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao atribuir usuário')
    } finally {
      setAssigning(false)
    }
  }

  async function onOnboardByUrl(e: React.FormEvent) {
    e.preventDefault()
    setOnboarding(true)
    setError(null)
    setLastOnboard(null)
    setLastOnboardKey(null)
    try {
      const keyUsed = (() => {
        const raw = (onboardIdempotencyKey || '').trim()
        if (raw) return raw
        try {
          const c: Crypto | undefined = typeof crypto !== 'undefined' ? crypto : undefined
          if (c && typeof c.randomUUID === 'function') {
            return c.randomUUID()
          }
        } catch {
          // ignore
        }
        return `auto-${Date.now()}`
      })()

      const res = await apiFetch('/super/onboarding/by-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          idempotency_key: keyUsed,
          name: onboardName,
          timezone: onboardTimezone,
          chatbot_domain: onboardDomain,
          allow_existing: onboardAllowExisting,
          template: onboardTemplate,
          flow_name: onboardFlowName,
          overwrite_flow: true,
          publish_flow: true,
          // passos opcionais (WA / invite) são feitos separadamente no checklist
        }),
      })

      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try {
          const js = await res.json()
          msg = js?.detail || js?.error?.code || js?.message || msg
        } catch {
          // ignore
        }
        throw new Error(msg)
      }

      const js = (await res.json()) as OnboardByUrlOut
      setLastOnboard(js)
      setLastOnboardKey(keyUsed)
      await loadTenants()
      try {
        setSelectedTenantId(js.tenant_id)
        setTenantId(String(js.tenant_id))
      } catch {
        // ignore
      }
      setOnboardName('')
      setOnboardAllowExisting(false)
      setOnboardIdempotencyKey('')
      setOnboardPhoneNumberId('')
      setOnboardWabaId('')
      setOnboardToken('')
      setOnboardInviteEmail('')
      setOnboardInviteExpiresHours(72)
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha no onboarding')
    } finally {
      setOnboarding(false)
    }
  }

  async function onCheckOnboardingRun() {
    const key = (lastOnboardKey || '').trim()
    if (!key) return
    setError(null)
    try {
      const res = await apiFetch(`/super/onboarding-runs/${encodeURIComponent(key)}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const js = (await res.json()) as OnboardingRunOut
      window.alert(`OnboardingRun (${js.idempotency_key})\nstatus=${js.status}\nerror=${js.error_code || '-'}\ntenant_id=${js.tenant_id ?? '-'}`)
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao consultar onboarding run')
    }
  }

  const [waAccounts, setWaAccounts] = useState<WhatsAppAccount[]>([])
  const [waLoading, setWaLoading] = useState(false)

  const [waPhoneNumberId, setWaPhoneNumberId] = useState('')
  const [waToken, setWaToken] = useState('')
  const [waWabaId, setWaWabaId] = useState('')
  const [waCreating, setWaCreating] = useState(false)

  const [inviteEmail, setInviteEmail] = useState('')
  const [inviting, setInviting] = useState(false)
  const [lastInvite, setLastInvite] = useState<InviteAdminOut | null>(null)

  const [onboardName, setOnboardName] = useState('')
  const [onboardTimezone, setOnboardTimezone] = useState('America/Sao_Paulo')
  const [availableTemplates, setAvailableTemplates] = useState<ChatbotTemplate[]>([])
  const [availableDomains, setAvailableDomains] = useState<ChatbotDomain[]>([])
  const [onboardDomain, setOnboardDomain] = useState<ChatbotDomain>('real_estate')
  const [onboardTemplate, setOnboardTemplate] = useState('default')
  const [onboardFlowName, setOnboardFlowName] = useState('default')
  const [onboardAllowExisting, setOnboardAllowExisting] = useState(false)
  const [onboardIdempotencyKey, setOnboardIdempotencyKey] = useState('')
  const [onboardPhoneNumberId, setOnboardPhoneNumberId] = useState('')
  const [onboardWabaId, setOnboardWabaId] = useState('')
  const [onboardToken, setOnboardToken] = useState('')
  const [onboardInviteEmail, setOnboardInviteEmail] = useState('')
  const [onboardInviteExpiresHours, setOnboardInviteExpiresHours] = useState<number>(72)

  const [onboarding, setOnboarding] = useState(false)
  const [lastOnboard, setLastOnboard] = useState<OnboardByUrlOut | null>(null)
  const [lastOnboardKey, setLastOnboardKey] = useState<string | null>(null)

  useEffect(() => {
    if (!lastOnboard) return
    setWizardTenantId(lastOnboard.tenant_id)
    setWizardWhatsAppAccountId(null)
    setWizardInviteEmail(lastOnboard.invite_email || null)
    setWizardInviteToken(lastOnboard.invite_token || null)

    // Ingestão removida da UI
  }, [lastOnboard])

  const [assignEmail, setAssignEmail] = useState('')
  const [assigning, setAssigning] = useState(false)
  const [lastAssign, setLastAssign] = useState<AssignUserOut | null>(null)

  useEffect(() => {
    if (!authed) navigate('/login')
  }, [authed, navigate])

  async function loadTenants() {
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch('/super/tenants')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const js = (await res.json()) as Tenant[]
      setTenants(js)
      if (js.length > 0 && selectedTenantId == null) {
        const active = tenantId ? js.find(t => t.id === parseInt(tenantId, 10)) : null
        setSelectedTenantId((active || js[0] || null)?.id ?? null)
      }
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao carregar tenants')
    } finally {
      setLoading(false)
    }
  }

  async function loadWhatsAppAccounts(tid: number) {
    setWaLoading(true)
    try {
      const res = await apiFetch(`/super/tenants/${tid}/whatsapp-accounts`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const js = (await res.json()) as WhatsAppAccount[]
      setWaAccounts(js)
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao carregar whatsapp accounts')
    } finally {
      setWaLoading(false)
    }
  }

  useEffect(() => {
    loadTenants()
    loadTemplates()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function loadTemplates() {
    try {
      const res = await apiFetch('/super/chatbot-templates')
      if (!res.ok) return
      const js = (await res.json()) as ChatbotTemplate[]
      const list = Array.isArray(js) ? js : []
      setAvailableTemplates(list)
      const domains = Array.from(new Set(list.map(x => x.domain))).sort()
      setAvailableDomains(domains)

      // Defaults seguros (mantém real_estate como fallback)
      if (domains.length > 0) {
        const preferred = domains.includes('car_dealer') ? 'car_dealer' : domains[0]!
        setOnboardDomain(preferred)
        const templatesForPreferred = list.filter(x => x.domain === preferred).map(x => x.template)
        if (templatesForPreferred.includes('default')) setOnboardTemplate('default')
        else if (templatesForPreferred.length > 0) setOnboardTemplate(templatesForPreferred[0]!)
      }
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    if (selectedTenantId != null) loadWhatsAppAccounts(selectedTenantId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTenantId])

  async function onCreateTenant(e: React.FormEvent) {
    e.preventDefault()
    setCreating(true)
    setError(null)
    try {
      const res = await apiFetch('/super/tenants', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, timezone }),
      })
      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try {
          const js = await res.json()
          msg = js?.detail || js?.message || msg
        } catch {
          // ignore
        }
        throw new Error(msg)
      }
      setName('')
      setTimezone('America/Sao_Paulo')
      await loadTenants()
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao criar tenant')
    } finally {
      setCreating(false)
    }
  }

  async function onCreateWhatsAppAccount(e: React.FormEvent) {
    e.preventDefault()
    if (selectedTenantId == null) return
    setWaCreating(true)
    setError(null)
    try {
      const res = await apiFetch(`/super/tenants/${selectedTenantId}/whatsapp-accounts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone_number_id: waPhoneNumberId,
          token: waToken || undefined,
          waba_id: waWabaId || undefined,
          is_active: true,
        }),
      })
      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try {
          const js = await res.json()
          msg = js?.detail || js?.message || msg
        } catch {
          // ignore
        }
        throw new Error(msg)
      }
      setWaPhoneNumberId('')
      setWaToken('')
      setWaWabaId('')
      await loadWhatsAppAccounts(selectedTenantId)
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao criar whatsapp account')
    } finally {
      setWaCreating(false)
    }
  }

  async function onInviteAdmin(e: React.FormEvent) {
    e.preventDefault()
    if (selectedTenantId == null) return
    setInviting(true)
    setError(null)
    try {
      const res = await apiFetch(`/super/tenants/${selectedTenantId}/invite-admin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: inviteEmail, expires_hours: 72 }),
      })
      if (!res.ok) {
        let msg = `HTTP ${res.status}`
        try {
          const js = await res.json()
          msg = js?.detail || js?.message || msg
        } catch {
          // ignore
        }
        throw new Error(msg)
      }
      const js = (await res.json()) as InviteAdminOut
      setLastInvite(js)
      setInviteEmail('')
    } catch (e) {
      const err = e as Error
      setError(err?.message || 'falha ao convidar admin')
    } finally {
      setInviting(false)
    }
  }

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-800">Tenants (Super Admin)</h1>
        <div className="text-sm text-slate-500">Onboarding e credenciais WhatsApp</div>
      </header>

      {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card space-y-4">
          <div className="card-header">Onboarding por URL</div>
          <form className="space-y-3" onSubmit={onOnboardByUrl}>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Nome do tenant</label>
              <input className="input" value={onboardName} onChange={e => setOnboardName(e.target.value)} required disabled={onboarding} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Timezone</label>
              <input className="input" value={onboardTimezone} onChange={e => setOnboardTimezone(e.target.value)} disabled={onboarding} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Domínio do chatbot</label>
              <select
                className="input"
                value={onboardDomain}
                onChange={e => {
                  const nextDomain = String(e.target.value)
                  setOnboardDomain(nextDomain)
                  const templatesForDomain = availableTemplates.filter(t => t.domain === nextDomain).map(t => t.template)
                  if (!templatesForDomain.includes(onboardTemplate)) {
                    if (templatesForDomain.includes('default')) setOnboardTemplate('default')
                    else if (templatesForDomain.length > 0) setOnboardTemplate(templatesForDomain[0]!)
                  }
                }}
                disabled={onboarding}
              >
                {(availableDomains.length ? availableDomains : ['real_estate']).map(d => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Template</label>
                <select
                  className="input"
                  value={onboardTemplate}
                  onChange={e => setOnboardTemplate(String(e.target.value))}
                  disabled={onboarding}
                >
                  {(availableTemplates.filter(t => t.domain === onboardDomain).map(t => t.template) || ['default']).map(tpl => (
                    <option key={tpl} value={tpl}>{tpl}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Nome do flow</label>
                <input className="input" value={onboardFlowName} onChange={e => setOnboardFlowName(e.target.value)} disabled={onboarding} />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Idempotency key (opcional)</label>
              <input className="input" value={onboardIdempotencyKey} onChange={e => setOnboardIdempotencyKey(e.target.value)} disabled={onboarding} />
            </div>

            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={onboardAllowExisting} onChange={e => setOnboardAllowExisting(e.target.checked)} disabled={onboarding} />
              Permitir reuso do tenant (idempotente)
            </label>

            <button className="btn btn-primary w-full" disabled={onboarding}>
              {onboarding ? 'Executando...' : 'Criar e publicar flow'}
            </button>
          </form>

          {lastOnboard && (
            <div className="text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-2">
              <div>
                Tenant criado: <strong>{lastOnboard.tenant_name}</strong> (<strong>#{lastOnboard.tenant_id}</strong>)
              </div>
              <div>
                Domínio: <strong>{lastOnboard.chatbot_domain}</strong>
              </div>
              <div>
                Flow: <strong>#{lastOnboard.flow_id}</strong> • Published: <strong>{String(lastOnboard.published)}</strong>
              </div>

              <div className="border-t border-slate-200 pt-2 space-y-3">
                <div className="text-xs font-semibold text-slate-600">Checklist (opcional)</div>

                <div className="grid grid-cols-1 gap-2">
                  <div className="flex items-center justify-between">
                    <div>1) Tenant + Flow</div>
                    <div className="text-xs text-green-700">OK</div>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>2) WhatsApp</div>
                    <div className="text-xs">{wizardWhatsAppAccountId ? `OK (#${wizardWhatsAppAccountId})` : 'Pendente'}</div>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>3) Invite admin</div>
                    <div className="text-xs">{wizardInviteToken ? 'OK' : 'Pendente'}</div>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2">
                    <div className="text-xs font-semibold text-slate-600">2) Criar WhatsApp Account</div>
                    <form className="space-y-2" onSubmit={onWizardCreateWhatsAppAccount}>
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1">Phone Number ID</label>
                        <input className="input" value={onboardPhoneNumberId} onChange={e => setOnboardPhoneNumberId(e.target.value)} required />
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">WABA ID (opcional)</label>
                          <input className="input" value={onboardWabaId} onChange={e => setOnboardWabaId(e.target.value)} />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">Token (opcional)</label>
                          <input className="input" value={onboardToken} onChange={e => setOnboardToken(e.target.value)} />
                        </div>
                      </div>
                      <button className="btn btn-ghost" type="submit" disabled={!wizardTenantId}>Criar WhatsApp</button>
                    </form>
                  </div>

                  <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2">
                    <div className="text-xs font-semibold text-slate-600">3) Convidar admin</div>
                    <form className="space-y-2" onSubmit={onWizardInviteAdmin}>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">Email do admin</label>
                          <input className="input" value={onboardInviteEmail} onChange={e => setOnboardInviteEmail(e.target.value)} required />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-slate-700 mb-1">Expira (horas)</label>
                          <input className="input" type="number" min={1} max={168} value={onboardInviteExpiresHours} onChange={e => setOnboardInviteExpiresHours(Number(e.target.value) || 72)} />
                        </div>
                      </div>
                      <button className="btn btn-ghost" type="submit" disabled={!wizardTenantId}>Gerar convite</button>
                    </form>
                    {wizardInviteToken && (
                      <div className="space-y-1">
                        <div>
                          Invite: <strong>{wizardInviteEmail}</strong>
                        </div>
                        <div className="text-xs text-slate-600">
                          Link de aceite: <code className="break-all">{`/accept-invite?token=${encodeURIComponent(String(wizardInviteToken || ''))}`}</code>
                        </div>
                        <div className="flex items-center gap-2">
                          <input className="input" value={wizardInviteToken} readOnly />
                          <button
                            type="button"
                            className="btn btn-ghost"
                            onClick={async () => {
                              try {
                                await navigator.clipboard.writeText(String(wizardInviteToken || ''))
                              } catch {
                                // ignore
                              }
                            }}
                          >
                            Copiar token
                          </button>
                          <button
                            type="button"
                            className="btn btn-ghost"
                            onClick={() => {
                              const url = `/accept-invite?token=${encodeURIComponent(String(wizardInviteToken || ''))}`
                              window.open(url, '_blank')
                            }}
                          >
                            Abrir aceite
                          </button>
                          <button
                            type="button"
                            className="btn btn-ghost"
                            onClick={async () => {
                              try {
                                const url = `${window.location.origin}/accept-invite?token=${encodeURIComponent(String(wizardInviteToken || ''))}`
                                await navigator.clipboard.writeText(url)
                              } catch {
                                // ignore
                              }
                            }}
                          >
                            Copiar link
                          </button>
                        </div>
                      </div>
                    )}
                  </div>

                </div>
              </div>
              {lastOnboardKey && (
                <div className="space-y-1">
                  <div>
                    Idempotency key: <strong>{lastOnboardKey}</strong>
                  </div>
                  <div className="flex items-center gap-2">
                    <button type="button" className="btn btn-ghost" onClick={onCheckOnboardingRun}>
                      Ver status do run
                    </button>
                  </div>
                </div>
              )}
              <div className="flex items-center gap-2">
                <button
                  className="btn btn-ghost"
                  onClick={() => {
                    try {
                      setTenantId(String(lastOnboard.tenant_id))
                    } catch {
                      // ignore
                    }
                    navigate('/flows')
                  }}
                >
                  Abrir Flows
                </button>
                <button
                  className="btn btn-ghost"
                  onClick={() => {
                    try {
                      setTenantId(String(lastOnboard.tenant_id))
                    } catch {
                      // ignore
                    }
                    navigate('/catalog/admin')
                  }}
                >
                  Abrir Catálogo Admin
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="card space-y-4">
          <div className="card-header">Criar tenant</div>
          <form className="space-y-3" onSubmit={onCreateTenant}>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Nome</label>
              <input className="input" value={name} onChange={e => setName(e.target.value)} required />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Timezone</label>
              <input className="input" value={timezone} onChange={e => setTimezone(e.target.value)} />
            </div>
            <button className="btn btn-primary w-full" disabled={creating}>
              {creating ? 'Criando...' : 'Criar'}
            </button>
          </form>
        </div>

        <div className="card space-y-3 lg:col-span-2">
          <div className="flex items-center justify-between">
            <div className="card-header">Tenants</div>
            <button className="btn btn-ghost" onClick={loadTenants} disabled={loading}>Atualizar</button>
          </div>

          {loading ? (
            <div className="text-sm text-slate-500">Carregando...</div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {tenants.map(t => (
                <div
                  key={t.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedTenantId(t.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      setSelectedTenantId(t.id)
                    }
                  }}
                  className={`text-left rounded-xl border p-4 transition-all-smooth ${
                    selectedTenantId === t.id ? 'border-primary-400 bg-primary-50' : 'border-slate-200 bg-white hover:bg-slate-50'
                  }`}
                >
                  <div className="text-sm font-semibold text-slate-800">{t.name}</div>
                  <div className="text-xs text-slate-500">#{t.id} • {t.timezone}</div>
                  <div className="mt-2">
                    <span className={`badge ${t.is_active ? 'badge-success' : 'badge-warning'}`}>
                      {t.is_active ? 'Ativo' : 'Suspenso'}
                    </span>
                  </div>

                  {selectedTenantId === t.id && (
                    <div className="mt-3 border-t border-slate-200 pt-3">
                      <button
                        type="button"
                        className="btn btn-sm btn-secondary w-full"
                        onClick={(e) => {
                          e.stopPropagation();
                          setTenantId(String(t.id));
                          navigate('/leads');
                        }}>
                        Entrar neste tenant
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="border-t border-slate-200 pt-4" />

          <div className="card-header">Atribuir usuário existente ao tenant</div>
          <form className="space-y-3" onSubmit={onAssignUser}>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
              <input className="input" type="email" value={assignEmail} onChange={e => setAssignEmail(e.target.value)} required />
            </div>
            <button className="btn btn-ghost w-full" disabled={assigning || selectedTenantId == null}>
              {assigning ? 'Atribuindo...' : 'Atribuir ao tenant selecionado'}
            </button>
          </form>

          {lastAssign && (
            <div className="text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-3">
              Usuário <strong>{lastAssign.email}</strong> agora está no tenant <strong>#{lastAssign.tenant_id}</strong>.<br />
              <span className="text-xs text-slate-500">Dica: faça logout/login para o painel carregar o tenant correto.</span>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="card space-y-4 lg:col-span-2">
          <div className="flex items-center justify-between">
            <div className="card-header">WhatsApp Accounts</div>
            {selectedTenant && (
              <div className="flex items-center gap-3">
                <div className="text-xs text-slate-500">Tenant: {selectedTenant.name} (#{selectedTenant.id})</div>
                <button className="btn btn-ghost" onClick={onOpenFlows}>Abrir Flows</button>
              </div>
            )}
          </div>

          {selectedTenant && (
            <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-2">
              <div className="text-xs font-semibold text-slate-600">Domínio do chatbot</div>
              <div className="flex flex-col md:flex-row md:items-center gap-2">
                <select
                  className="input"
                  value={selectedTenantDomain}
                  onChange={(e) => setSelectedTenantDomain(e.target.value)}
                  disabled={domainLoading}
                >
                  {(supportedDomains.length ? supportedDomains : ['real_estate']).map((d) => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
                <button
                  className="btn btn-ghost"
                  type="button"
                  disabled={domainLoading || !selectedTenantId}
                  onClick={saveSelectedTenantDomain}
                >
                  {domainLoading ? 'Salvando...' : 'Salvar domínio'}
                </button>
              </div>

              <div className="border-t border-slate-200 pt-3" />

              <div className="text-xs font-semibold text-slate-600">Domínios habilitados</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {(supportedDomains.length ? supportedDomains : ['real_estate']).map((d) => {
                  const checked = selectedTenantEnabledDomains.includes(d)
                  const disabled = d === selectedTenantDomain
                  return (
                    <label key={d} className="flex items-center gap-2 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={disabled || domainLoading}
                        onChange={(e) => {
                          const next = e.target.checked
                            ? Array.from(new Set([...selectedTenantEnabledDomains, d]))
                            : selectedTenantEnabledDomains.filter((x) => x !== d)
                          setSelectedTenantEnabledDomains(next)
                        }}
                      />
                      <span>{d}{disabled ? ' (ativo)' : ''}</span>
                    </label>
                  )
                })}
              </div>

              <div className="flex items-center gap-2">
                <button
                  className="btn btn-ghost"
                  type="button"
                  disabled={domainLoading || !selectedTenantId}
                  onClick={saveSelectedTenantEnabledDomains}
                >
                  {domainLoading ? 'Salvando...' : 'Salvar domínios habilitados'}
                </button>
              </div>

              {selectedTenantDomainStatus.length > 0 && (
                <div className="border-t border-slate-200 pt-3 space-y-2">
                  <div className="text-xs font-semibold text-slate-600">Status por domínio</div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {selectedTenantDomainStatus.map((s) => (
                      <div key={s.domain} className="rounded-lg border border-slate-200 bg-slate-50 p-2 text-sm">
                        <div className="font-medium text-slate-800">{s.domain}</div>
                        <div className="text-xs text-slate-600">
                          Published: <strong>{String(s.has_published_flow)}</strong>
                          {' • '}Kanban: <strong>{String(s.has_lead_kanban)}</strong>
                          {' • '}Resumo: <strong>{String(s.has_lead_summary)}</strong>
                        </div>
                        <div className="mt-2 flex items-center gap-2">
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            disabled={domainLoading || !selectedTenantId}
                            onClick={() => applyDefaultTemplateForDomain(s.domain)}
                          >
                            Aplicar template default
                          </button>
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            disabled={domainLoading || !selectedTenantId}
                            onClick={() => reloadSelectedTenantDomains(selectedTenantId)}
                          >
                            Recarregar
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {domainError && <div className="text-xs text-red-700">{domainError}</div>}
            </div>
          )}

          {selectedTenant && (
            <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div className="text-sm text-slate-700">
                Status do tenant: <strong>{selectedTenant.is_active ? 'Ativo' : 'Suspenso'}</strong>
              </div>
              <button
                className={`btn ${selectedTenant.is_active ? 'btn-warning' : 'btn-success'}`}
                onClick={() => {
                  const action = selectedTenant.is_active ? 'suspender' : 'reativar';
                  if (window.confirm(`Tem certeza que deseja ${action} o acesso para o tenant "${selectedTenant.name}"?`)) {
                    setTenantActive(selectedTenant.id, !selectedTenant.is_active)
                  }
                }}
              >
                {selectedTenant.is_active ? 'Suspender acesso' : 'Reativar acesso'}
              </button>
            </div>
          )}

          {waLoading ? (
            <div className="text-sm text-slate-500">Carregando...</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="table min-w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-600">
                    <th className="py-2 pr-3">ID</th>
                    <th className="py-2 pr-3">phone_number_id</th>
                    <th className="py-2 pr-3">waba_id</th>
                    <th className="py-2 pr-3">Ativo</th>
                  </tr>
                </thead>
                <tbody>
                  {waAccounts.map(a => (
                    <tr key={a.id} className="table-row">
                      <td className="py-2 pr-3">{a.id}</td>
                      <td className="py-2 pr-3 font-mono text-xs">{a.phone_number_id}</td>
                      <td className="py-2 pr-3 font-mono text-xs">{a.waba_id || '-'}</td>
                      <td className="py-2 pr-3">{a.is_active ? 'Sim' : 'Não'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!waAccounts.length && <div className="text-sm text-slate-500 mt-3">Nenhuma conta cadastrada.</div>}
            </div>
          )}

          <form className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end" onSubmit={onCreateWhatsAppAccount}>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-1">phone_number_id</label>
              <input className="input" value={waPhoneNumberId} onChange={e => setWaPhoneNumberId(e.target.value)} required />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">waba_id</label>
              <input className="input" value={waWabaId} onChange={e => setWaWabaId(e.target.value)} />
            </div>
            <div>
              <button className="btn btn-primary w-full" disabled={waCreating || selectedTenantId == null}>
                {waCreating ? 'Salvando...' : 'Adicionar'}
              </button>
            </div>
            <div className="md:col-span-4">
              <label className="block text-sm font-medium text-slate-700 mb-1">Token (opcional)</label>
              <input className="input" value={waToken} onChange={e => setWaToken(e.target.value)} placeholder="Armazene com cuidado (produção: use secret manager)" />
            </div>
          </form>
        </div>

        <div className="card space-y-4">
          <div className="card-header">Atribuir usuário existente ao tenant</div>
          <form className="space-y-3" onSubmit={onAssignUser}>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
              <input className="input" type="email" value={assignEmail} onChange={e => setAssignEmail(e.target.value)} required placeholder="email@exemplo.com" />
            </div>
            <button className="btn btn-ghost w-full" disabled={assigning || selectedTenantId == null}>
              {assigning ? 'Atribuindo...' : 'Atribuir ao tenant selecionado'}
            </button>
          </form>
          {lastAssign && (
            <div className="text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-3">
              Usuário <strong>{lastAssign.email}</strong> agora está no tenant <strong>#{lastAssign.tenant_id}</strong>.<br />
              <span className="text-xs text-slate-500">Dica: faça logout/login para o painel carregar o tenant correto.</span>
            </div>
          )}
          <div className="border-t border-slate-200 my-4" />
          <div className="card-header">Convidar admin do tenant</div>
          <form className="space-y-3" onSubmit={onInviteAdmin}>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
              <input className="input" type="email" value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} required />
            </div>
            <button className="btn btn-primary w-full" disabled={inviting || selectedTenantId == null}>
              {inviting ? 'Gerando...' : 'Gerar convite'}
            </button>
          </form>

          {lastInvite && (
            <div className="text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-3">
              Token gerado para <strong>{lastInvite.email}</strong><br />
              <div className="mt-2">
                <div className="text-xs text-slate-500">Link:</div>
                <code className="break-all">/accept-invite?token={lastInvite.token}</code>
              </div>
              <div className="mt-2">
                <div className="text-xs text-slate-500">Token:</div>
                <code className="break-all">{lastInvite.token}</code>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
