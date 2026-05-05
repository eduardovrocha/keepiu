import { useState, useEffect } from 'react'
import {
  MessageCircle, CheckCircle2, XCircle, Copy, Eye, EyeOff,
  Save, RefreshCw, AlertCircle, ExternalLink,
} from 'lucide-react'
import { Card } from '../Card'
import { cn } from '../../utils/cn'
import { useSettings, useRevealAllSettings, useUpdateSettings } from '../../hooks/useSettings'

const WA_FIELDS: { key: string; label: string; secret: boolean; placeholder: string; description: string }[] = [
  {
    key: 'whatsapp_access_token',
    label: 'Access Token',
    secret: true,
    placeholder: 'EAAxxxx...',
    description: 'Token de acesso permanente da sua app Meta.',
  },
  {
    key: 'whatsapp_phone_number_id',
    label: 'Phone Number ID',
    secret: false,
    placeholder: '1234567890',
    description: 'ID numérico do número WhatsApp Business.',
  },
  {
    key: 'whatsapp_verify_token',
    label: 'Verify Token',
    secret: true,
    placeholder: 'meu-token-secreto',
    description: 'Token usado na verificação do webhook pelo Meta.',
  },
  {
    key: 'whatsapp_app_secret',
    label: 'App Secret',
    secret: true,
    placeholder: 'abc123def456...',
    description: 'Segredo da app — usado para validar assinatura HMAC dos webhooks.',
  },
]

function WebhookUrlRow({ url }: { url: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-2">
      <span className="flex-1 font-mono text-xs text-muted-foreground truncate">{url}</span>
      <button
        onClick={() => {
          navigator.clipboard.writeText(url)
          setCopied(true)
          setTimeout(() => setCopied(false), 2000)
        }}
        className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
        title="Copiar"
      >
        {copied ? <CheckCircle2 className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
      </button>
    </div>
  )
}

export function WhatsAppCard({ noCard = false }: { noCard?: boolean }) {
  const { data: settingsList } = useSettings(true)
  const { data: revealedData } = useRevealAllSettings(true)
  const updateMutation = useUpdateSettings()

  const [fieldValues, setFieldValues] = useState<Record<string, string>>({})
  const [dirtyKeys, setDirtyKeys] = useState<Set<string>>(new Set())
  const [savingKeys, setSavingKeys] = useState<Set<string>>(new Set())
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({})
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null)

  useEffect(() => {
    if (!settingsList) return
    const revealed = revealedData?.values ?? {}
    setFieldValues((prev) => {
      const next = { ...prev }
      for (const f of WA_FIELDS) {
        if (dirtyKeys.has(f.key)) continue
        if (f.secret) {
          next[f.key] = revealed[f.key] ?? ''
        } else {
          const row = settingsList.find((s) => s.key === f.key)
          next[f.key] = row?.display_value ?? ''
        }
      }
      return next
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settingsList, revealedData])

  const settingsMap = Object.fromEntries((settingsList ?? []).map((s) => [s.key, s]))
  const isConfigured = ['whatsapp_access_token', 'whatsapp_phone_number_id', 'whatsapp_verify_token'].every(
    (k) => settingsMap[k]?.has_value,
  )

  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  const webhookUrl = `${apiUrl}/webhooks/whatsapp`

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 3500)
  }

  const handleChange = (key: string, value: string) => {
    setFieldValues((prev) => ({ ...prev, [key]: value }))
    setDirtyKeys((prev) => new Set(prev).add(key))
  }

  const saveKey = async (key: string) => {
    const value = fieldValues[key]?.trim()
    if (!value) return
    setSavingKeys((prev) => new Set(prev).add(key))
    try {
      await updateMutation.mutateAsync([{ key, value }])
      setDirtyKeys((prev) => {
        const n = new Set(prev)
        n.delete(key)
        return n
      })
      showToast('Configuração salva com sucesso', true)
    } catch {
      showToast('Falha ao salvar', false)
    } finally {
      setSavingKeys((prev) => {
        const n = new Set(prev)
        n.delete(key)
        return n
      })
    }
  }

  const content = (
    <>
      {/* Fields */}
      <div className="space-y-5">
        {WA_FIELDS.map((field) => {
          const isDirty = dirtyKeys.has(field.key)
          const isSaving = savingKeys.has(field.key)
          const hasSaved = settingsMap[field.key]?.has_value
          const show = showKeys[field.key] ?? false

          return (
            <div key={field.key} className="space-y-1.5">
              <label className="flex items-center gap-2 text-sm font-medium text-foreground">
                {field.label}
                {hasSaved && !isDirty && (
                  <span className="inline-flex items-center gap-1 text-xs text-green-600 font-normal">
                    <CheckCircle2 className="w-3 h-3" />
                    Salvo
                  </span>
                )}
              </label>
              <p className="text-xs text-muted-foreground">{field.description}</p>
              <div className="flex items-center gap-2">
                <input
                  type={field.secret && !show ? 'password' : 'text'}
                  value={fieldValues[field.key] ?? ''}
                  onChange={(e) => handleChange(field.key, e.target.value)}
                  placeholder={field.placeholder}
                  autoComplete="off"
                  spellCheck={false}
                  className={cn(
                    'flex-1 px-3 py-2 rounded-lg border bg-background text-sm font-mono transition-colors',
                    'focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/50',
                    'border-border',
                  )}
                />
                {field.secret && (
                  <button
                    type="button"
                    onClick={() => setShowKeys((prev) => ({ ...prev, [field.key]: !prev[field.key] }))}
                    className="p-2 rounded-lg border border-border hover:bg-muted transition-colors text-muted-foreground hover:text-foreground shrink-0"
                    title={show ? 'Ocultar' : 'Mostrar'}
                  >
                    {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => saveKey(field.key)}
                  disabled={!isDirty || isSaving}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors shrink-0',
                    isDirty && !isSaving
                      ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                      : 'bg-muted text-muted-foreground cursor-not-allowed opacity-50',
                  )}
                >
                  {isSaving ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Save className="w-3.5 h-3.5" />
                  )}
                  Salvar
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {/* Webhook URL */}
      <div className="mt-5 pt-5 border-t border-border space-y-1.5">
        <label className="block text-sm font-medium text-foreground">URL do Webhook</label>
        <p className="text-xs text-muted-foreground">
          Registre esta URL no Meta for Developers → WhatsApp → Configuration → Webhook.
          Deve ser HTTPS e acessível publicamente.
        </p>
        <WebhookUrlRow url={webhookUrl} />
        <a
          href="https://developers.facebook.com/apps"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm text-green-700 hover:underline mt-1"
        >
          <ExternalLink className="w-3.5 h-3.5" />
          Abrir Meta for Developers
        </a>
      </div>

      {/* Toast */}
      {toast && (
        <div
          className={cn(
            'mt-4 flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm border',
            toast.ok
              ? 'bg-green-50 text-green-800 border-green-200'
              : 'bg-red-50 text-red-800 border-red-200',
          )}
        >
          {toast.ok ? (
            <CheckCircle2 className="w-4 h-4 shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0" />
          )}
          {toast.msg}
        </div>
      )}
    </>
  )

  if (noCard) return content

  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-5">
        <div className="p-2 rounded-lg bg-green-50 border border-green-100">
          <MessageCircle className="w-4 h-4 text-green-600" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-foreground">WhatsApp Business</h2>
          <p className="text-xs text-muted-foreground">Integração com Meta Cloud API</p>
        </div>
        <span
          className={cn(
            'ml-auto inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
            isConfigured ? 'bg-green-100 text-green-700' : 'bg-muted text-muted-foreground',
          )}
        >
          {isConfigured ? (
            <><CheckCircle2 className="w-3 h-3" /> Configurado</>
          ) : (
            <><XCircle className="w-3 h-3" /> Não configurado</>
          )}
        </span>
      </div>
      {content}
    </Card>
  )
}
