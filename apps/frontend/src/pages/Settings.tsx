import { useState, useEffect, useCallback } from 'react'
import {
  Eye, EyeOff, Copy, Check, Save, RefreshCw, ExternalLink,
  Bot, Key, Webhook, AlertCircle, CheckCircle2, X, Activity,
  XCircle, Loader2, ShieldOff, ChevronDown, MessageCircle, Mic,
} from 'lucide-react'
import { Card } from '../components/Card'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { WhatsAppCard } from '../components/settings/WhatsAppCard'
import { cn } from '../utils/cn'
import {
  useSettings,
  useRevealAllSettings,
  useUpdateSettings,
  useTestSettings,
} from '../hooks/useSettings'
import { useAuthStore } from '../store/authStore'
import { SystemSetting, CheckResult } from '../types'

// ── Toast ──────────────────────────────────────────────────────────────────────

interface Toast {
  id: string
  message: string
  type: 'success' | 'error'
}

function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([])

  const add = useCallback((message: string, type: Toast['type'] = 'success') => {
    const id = Date.now().toString()
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000)
  }, [])

  const remove = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return { toasts, add, remove }
}

function ToastContainer({ toasts, remove }: { toasts: Toast[]; remove: (id: string) => void }) {
  if (!toasts.length) return null
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={cn(
            'flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg text-sm font-medium pointer-events-auto',
            'animate-fade-in border',
            t.type === 'success'
              ? 'bg-green-50 text-green-800 border-green-200'
              : 'bg-red-50 text-red-800 border-red-200'
          )}
        >
          {t.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 shrink-0 text-green-600" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
          )}
          <span>{t.message}</span>
          <button
            onClick={() => remove(t.id)}
            className="ml-1 hover:opacity-70 transition-opacity"
            aria-label="Dismiss"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>
  )
}

// ── SettingField ───────────────────────────────────────────────────────────────

interface SettingFieldProps {
  label: string
  description?: string
  settingKey: string
  setting?: SystemSetting
  value: string
  onChange: (key: string, value: string) => void
  onSave: (key: string) => void
  isSaving: boolean
  isDirty: boolean
  isSecret?: boolean
  placeholder?: string
  hint?: string
  copyable?: boolean
  openable?: boolean
  validation?: (v: string) => string | null
}

function SettingField({
  label,
  description,
  settingKey,
  setting,
  value,
  onChange,
  onSave,
  isSaving,
  isDirty,
  isSecret = false,
  placeholder,
  hint,
  copyable = false,
  openable = false,
  validation,
}: SettingFieldProps) {
  const [showValue, setShowValue] = useState(false)
  const [copied, setCopied] = useState(false)

  const validationError = validation ? validation(value) : null
  const inputType = isSecret && !showValue ? 'password' : 'text'

  const handleCopy = () => {
    if (!value) return
    navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-1.5">
      <label className="flex items-center gap-2 text-sm font-medium text-foreground">
        {label}
        {setting?.has_value && !isDirty && (
          <span className="inline-flex items-center gap-1 text-xs text-green-600 font-normal">
            <CheckCircle2 className="w-3 h-3" />
            Saved
          </span>
        )}
      </label>

      {description && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}

      <div className="flex items-center gap-2">
        <input
          type={inputType}
          value={value}
          onChange={(e) => onChange(settingKey, e.target.value)}
          placeholder={placeholder}
          autoComplete="off"
          spellCheck={false}
          className={cn(
            'flex-1 px-3 py-2 rounded-lg border bg-background text-sm transition-colors font-mono',
            'focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/50',
            validationError && isDirty
              ? 'border-red-400 focus:ring-red-200'
              : 'border-border'
          )}
        />

        {isSecret && (
          <button
            type="button"
            onClick={() => setShowValue((v) => !v)}
            className="p-2 rounded-lg border border-border hover:bg-muted transition-colors text-muted-foreground hover:text-foreground shrink-0"
            title={showValue ? 'Hide' : 'Show'}
          >
            {showValue ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        )}

        {(copyable || isSecret) && (
          <button
            type="button"
            onClick={handleCopy}
            disabled={!value}
            className="p-2 rounded-lg border border-border hover:bg-muted transition-colors text-muted-foreground hover:text-foreground shrink-0 disabled:opacity-40 disabled:cursor-not-allowed"
            title="Copy"
          >
            {copied ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
          </button>
        )}

        {openable && value && (
          <a
            href={value}
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 rounded-lg border border-border hover:bg-muted transition-colors text-muted-foreground hover:text-foreground shrink-0"
            title="Open"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        )}

        <button
          type="button"
          onClick={() => onSave(settingKey)}
          disabled={!isDirty || isSaving || !!validationError}
          className={cn(
            'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors shrink-0',
            isDirty && !validationError
              ? 'bg-primary text-primary-foreground hover:bg-primary/90'
              : 'bg-muted text-muted-foreground cursor-not-allowed opacity-50'
          )}
        >
          {isSaving ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Save className="w-3.5 h-3.5" />
          )}
          Save
        </button>
      </div>

      {validationError && isDirty && (
        <p className="text-xs text-red-600 flex items-center gap-1">
          <AlertCircle className="w-3 h-3" />
          {validationError}
        </p>
      )}

      {hint && !validationError && (
        <p className="text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  )
}

// ── ToggleSetting ──────────────────────────────────────────────────────────────

interface ToggleSettingProps {
  label: string
  description?: string
  settingKey: string
  value: string
  onToggle: (key: string, value: string) => void
  isSaving: boolean
  isDirty: boolean
}

function ToggleSetting({
  label, description, settingKey, value, onToggle, isSaving, isDirty,
}: ToggleSettingProps) {
  const enabled = value === 'true'

  const handleToggle = () => {
    onToggle(settingKey, enabled ? 'false' : 'true')
  }

  return (
    <div className="flex items-start justify-between gap-4">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground">{label}</p>
        {description && <p className="text-xs text-muted-foreground mt-0.5">{description}</p>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        onClick={handleToggle}
        disabled={isSaving}
        className={cn(
          'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent',
          'transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary/30',
          enabled ? 'bg-primary' : 'bg-muted',
          isSaving && 'opacity-50 cursor-not-allowed',
        )}
      >
        <span
          className={cn(
            'pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-md',
            'transform transition duration-200 ease-in-out',
            enabled ? 'translate-x-5' : 'translate-x-0',
          )}
        />
      </button>
      {isSaving && <RefreshCw className="w-3.5 h-3.5 animate-spin text-muted-foreground shrink-0 self-center" />}
      {!isSaving && isDirty && <Check className="w-3.5 h-3.5 text-green-600 shrink-0 self-center" />}
    </div>
  )
}

// ── CollapsibleSection ─────────────────────────────────────────────────────────

function CollapsibleSection({
  title,
  subtitle,
  icon,
  badge,
  defaultOpen = false,
  children,
}: {
  title: string
  subtitle?: string
  icon: JSX.Element
  badge?: JSX.Element
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <Card className="overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 px-6 py-4 hover:bg-muted/30 transition-colors text-left"
      >
        {icon}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-foreground">{title}</p>
          {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
        </div>
        {badge}
        <ChevronDown
          className={cn(
            'w-4 h-4 text-muted-foreground shrink-0 transition-transform duration-200',
            open && 'rotate-180',
          )}
        />
      </button>
      <div
        className={cn(
          'grid transition-all duration-200',
          open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]',
        )}
      >
        <div className="overflow-hidden">
          <div className="border-t border-border px-6 py-5">
            {children}
          </div>
        </div>
      </div>
    </Card>
  )
}

// ── Health Check ───────────────────────────────────────────────────────────────

const CHECK_LABELS: Record<string, string> = {
  openai: 'OpenAI API',
  telegram: 'Telegram Bot',
  webhook_secret: 'Webhook Secret',
  bot_url: 'Bot URL',
}

function HealthCheckCard() {
  const testMutation = useTestSettings()
  const result = testMutation.data

  return (
    <div>
      <div className="flex justify-end mb-4">
        <button
          onClick={() => testMutation.mutate()}
          disabled={testMutation.isPending}
          className={cn(
            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
            testMutation.isPending
              ? 'bg-muted text-muted-foreground cursor-not-allowed'
              : 'bg-primary text-primary-foreground hover:bg-primary/90'
          )}
        >
          {testMutation.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Activity className="w-4 h-4" />
          )}
          {testMutation.isPending ? 'Testing…' : 'Run Health Check'}
        </button>
      </div>

      {!result && !testMutation.isPending && (
        <p className="text-sm text-muted-foreground text-center py-4">
          Click "Run Health Check" to validate all credentials.
        </p>
      )}

      {testMutation.isPending && (
        <div className="space-y-2">
          {Object.keys(CHECK_LABELS).map((key) => (
            <div
              key={key}
              className="flex items-center gap-3 px-4 py-3 rounded-lg bg-muted/50 animate-pulse"
            >
              <div className="w-4 h-4 rounded-full bg-muted" />
              <span className="text-sm text-muted-foreground">{CHECK_LABELS[key]}</span>
            </div>
          ))}
        </div>
      )}

      {result && !testMutation.isPending && (
        <div className="space-y-2">
          <div
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium mb-3',
              result.overall
                ? 'bg-green-50 text-green-800 border border-green-200'
                : 'bg-red-50 text-red-800 border border-red-200'
            )}
          >
            {result.overall ? (
              <CheckCircle2 className="w-4 h-4 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 shrink-0" />
            )}
            {result.overall
              ? 'All checks passed — system is ready'
              : 'Some checks failed — review the items below'}
          </div>
          {Object.entries(result.checks).map(([key, check]: [string, CheckResult]) => (
            <CheckRow key={key} label={CHECK_LABELS[key] ?? key} check={check} />
          ))}
        </div>
      )}

      {testMutation.isError && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
          <XCircle className="w-4 h-4 shrink-0" />
          {(testMutation.error as { response?: { status?: number } })?.response?.status === 403
            ? 'Admin access required to run health check.'
            : 'Failed to run health check. Ensure the backend is reachable.'}
        </div>
      )}
    </div>
  )
}

function CheckRow({ label, check }: { label: string; check: CheckResult }) {
  return (
    <div
      className={cn(
        'flex items-center gap-3 px-4 py-3 rounded-lg border',
        check.ok ? 'bg-green-50/60 border-green-100' : 'bg-red-50/60 border-red-100'
      )}
    >
      {check.ok ? (
        <CheckCircle2 className="w-4 h-4 shrink-0 text-green-600" />
      ) : (
        <XCircle className="w-4 h-4 shrink-0 text-red-500" />
      )}
      <div className="flex-1 min-w-0">
        <span className={cn('text-sm font-medium', check.ok ? 'text-green-800' : 'text-red-800')}>
          {label}
        </span>
        <p className={cn('text-xs mt-0.5', check.ok ? 'text-green-700' : 'text-red-700')}>
          {check.message}
        </p>
      </div>
    </div>
  )
}

// ── Validators ─────────────────────────────────────────────────────────────────

const validators: Record<string, (v: string) => string | null> = {
  telegram_bot_url: (v) => {
    if (!v) return null
    try { new URL(v); return null } catch { return 'Must be a valid URL (e.g. https://t.me/YourBotName)' }
  },
  openai_api_key: (v) => {
    if (!v) return null
    if (!v.startsWith('sk-')) return 'OpenAI API keys start with "sk-"'
    return null
  },
  telegram_bot_token: (v) => {
    if (!v) return null
    if (!/^\d+:[A-Za-z0-9_-]{35,}$/.test(v))
      return 'Expected: 1234567890:ABCDEFGhijklmnopqrstuvwxyz...'
    return null
  },
  telegram_webhook_secret: (v) => {
    if (!v) return null
    if (v.length < 16) return 'Minimum 16 characters required'
    return null
  },
}

// ── Settings Page ──────────────────────────────────────────────────────────────

export function Settings() {
  const isAdmin = useAuthStore((s) => s.isAdmin)
  const { data: settingsList, isLoading: settingsLoading } = useSettings(isAdmin)
  const { data: revealedData, isLoading: revealLoading } = useRevealAllSettings(isAdmin)
  const updateMutation = useUpdateSettings()
  const { toasts, add: addToast, remove: removeToast } = useToast()

  const [fieldValues, setFieldValues] = useState<Record<string, string>>({})
  const [dirtyKeys, setDirtyKeys] = useState<Set<string>>(new Set())
  const [savingKeys, setSavingKeys] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (!settingsList) return
    const revealed = revealedData?.values ?? {}
    setFieldValues((prev) => {
      const next = { ...prev }
      for (const s of settingsList) {
        if (dirtyKeys.has(s.key)) continue
        if (s.is_secret) {
          next[s.key] = revealed[s.key] ?? ''
        } else {
          next[s.key] = s.display_value ?? ''
        }
      }
      return next
    })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settingsList, revealedData])

  if (!isAdmin) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4 animate-fade-in">
        <div className="p-4 rounded-full bg-muted">
          <ShieldOff className="w-8 h-8 text-muted-foreground" />
        </div>
        <div className="text-center">
          <p className="text-base font-semibold text-foreground">Admin access required</p>
          <p className="text-sm text-muted-foreground mt-1">
            Settings are only available to admin accounts.
          </p>
          <p className="text-xs text-muted-foreground mt-3 font-mono bg-muted px-3 py-1.5 rounded-lg inline-block">
            Set INITIAL_ADMIN_USERNAME=your_username in .env and restart the backend.
          </p>
        </div>
      </div>
    )
  }

  const settingsMap = Object.fromEntries(
    (settingsList ?? []).map((s) => [s.key, s])
  )

  const waConfigured = ['whatsapp_access_token', 'whatsapp_phone_number_id', 'whatsapp_verify_token'].every(
    (k) => settingsMap[k]?.has_value,
  )

  const handleChange = (key: string, value: string) => {
    setFieldValues((prev) => ({ ...prev, [key]: value }))
    setDirtyKeys((prev) => new Set(prev).add(key))
  }

  const saveKey = async (key: string) => {
    const value = fieldValues[key]?.trim()
    if (!value) return
    const validator = validators[key]
    if (validator?.(value)) return

    setSavingKeys((prev) => new Set(prev).add(key))
    try {
      await updateMutation.mutateAsync([{ key, value }])
      setDirtyKeys((prev) => { const n = new Set(prev); n.delete(key); return n })
      addToast('Setting saved', 'success')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Failed to save'
      addToast(msg, 'error')
    } finally {
      setSavingKeys((prev) => { const n = new Set(prev); n.delete(key); return n })
    }
  }

  const saveAll = async () => {
    const updates = Array.from(dirtyKeys)
      .map((key) => ({ key, value: fieldValues[key]?.trim() ?? '' }))
      .filter(({ key, value }) => value && !validators[key]?.(value))
    if (!updates.length) return

    setSavingKeys(new Set(updates.map((u) => u.key)))
    try {
      await updateMutation.mutateAsync(updates)
      setDirtyKeys(new Set())
      addToast(`${updates.length} setting${updates.length > 1 ? 's' : ''} saved`, 'success')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Failed to save'
      addToast(msg, 'error')
    } finally {
      setSavingKeys(new Set())
    }
  }

  const hasDirty = dirtyKeys.size > 0
  const allValid = Array.from(dirtyKeys).every((key) => {
    const v = fieldValues[key]?.trim()
    return v && !validators[key]?.(v)
  })

  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  const webhookUrl = `${apiUrl}/webhooks/telegram`

  const isLoading = settingsLoading || revealLoading

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner />
      </div>
    )
  }

  const fieldProps = (key: string, isSecret = false) => ({
    settingKey: key,
    setting: settingsMap[key],
    value: fieldValues[key] ?? '',
    onChange: handleChange,
    onSave: saveKey,
    isSaving: savingKeys.has(key),
    isDirty: dirtyKeys.has(key),
    isSecret,
    validation: validators[key],
  })

  return (
    <div className="space-y-3 animate-fade-in max-w-2xl">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-2">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Settings</h1>
          <p className="text-muted-foreground mt-1">Configure your Keepiu integrations</p>
        </div>
        {hasDirty && (
          <button
            onClick={saveAll}
            disabled={!allValid || updateMutation.isPending}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
              allValid
                ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                : 'bg-muted text-muted-foreground cursor-not-allowed opacity-50'
            )}
          >
            {updateMutation.isPending ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            Save all
          </button>
        )}
      </div>

      {/* ── Telegram ────────────────────────────────────────────────────── */}
      <CollapsibleSection
        title="Telegram"
        subtitle="Bot connection and webhook settings"
        icon={
          <div className="p-2 rounded-lg bg-blue-50 border border-blue-100 shrink-0">
            <Bot className="w-4 h-4 text-blue-600" />
          </div>
        }
      >
        <div className="space-y-5">
          <SettingField
            label="Bot URL"
            description="Your Telegram bot link shared with users."
            placeholder="https://t.me/YourBotName"
            copyable
            openable
            hint="Example: https://t.me/KeepiuBot"
            {...fieldProps('telegram_bot_url')}
          />

          <SettingField
            label="Bot Token"
            description="Token from @BotFather. Never share this publicly."
            placeholder="1234567890:ABCDEFGhijklmnopqrstuvwxyz..."
            hint="Get yours at t.me/BotFather → /mybots → API Token"
            {...fieldProps('telegram_bot_token', true)}
          />

          <SettingField
            label="Webhook Secret"
            description="Secret header used to validate incoming updates."
            placeholder="at-least-16-chars-secret"
            hint="Minimum 16 characters. Set this in Telegram's setWebhook call."
            {...fieldProps('telegram_webhook_secret', true)}
          />

          <div className="pt-1">
            <label className="block text-sm font-medium text-foreground mb-1">
              Webhook URL
            </label>
            <p className="text-xs text-muted-foreground mb-1.5">
              Register this URL in Telegram — must be HTTPS and publicly accessible.
            </p>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={webhookUrl}
                readOnly
                className="flex-1 px-3 py-2 rounded-lg border bg-muted text-sm font-mono"
              />
              <CopyButton text={webhookUrl} />
            </div>
          </div>
        </div>
      </CollapsibleSection>

      {/* ── OpenAI ──────────────────────────────────────────────────────── */}
      <CollapsibleSection
        title="OpenAI"
        subtitle="AI analysis and embedding generation"
        icon={
          <div className="p-2 rounded-lg bg-violet-50 border border-violet-100 shrink-0">
            <Key className="w-4 h-4 text-violet-600" />
          </div>
        }
      >
        <SettingField
          label="API Key"
          description="Used for content analysis and semantic search embeddings."
          placeholder="sk-..."
          hint="Get yours at platform.openai.com → API Keys"
          {...fieldProps('openai_api_key', true)}
        />
      </CollapsibleSection>

      {/* ── WhatsApp ─────────────────────────────────────────────────────── */}
      <CollapsibleSection
        title="WhatsApp Business"
        subtitle="Integração com Meta Cloud API"
        icon={
          <div className="p-2 rounded-lg bg-green-50 border border-green-100 shrink-0">
            <MessageCircle className="w-4 h-4 text-green-600" />
          </div>
        }
        badge={
          <span
            className={cn(
              'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium mr-1',
              waConfigured ? 'bg-green-100 text-green-700' : 'bg-muted text-muted-foreground',
            )}
          >
            {waConfigured ? (
              <><CheckCircle2 className="w-3 h-3" /> Configurado</>
            ) : (
              <><XCircle className="w-3 h-3" /> Não configurado</>
            )}
          </span>
        }
      >
        <WhatsAppCard noCard />
      </CollapsibleSection>

      {/* ── Pipeline ─────────────────────────────────────────────────────── */}
      <CollapsibleSection
        title="Pipeline de Processamento"
        subtitle="Configurações de extração e análise de conteúdo"
        icon={
          <div className="p-2 rounded-lg bg-amber-50 border border-amber-100 shrink-0">
            <Mic className="w-4 h-4 text-amber-600" />
          </div>
        }
      >
        <ToggleSetting
          label="Transcrição de áudios"
          description="Ativa a extração e transcrição automática de áudio de vídeos e mensagens de voz."
          settingKey="audio_transcription_enabled"
          value={fieldValues['audio_transcription_enabled'] ?? 'false'}
          onToggle={async (key, val) => {
            handleChange(key, val)
            setSavingKeys((prev) => new Set(prev).add(key))
            try {
              await updateMutation.mutateAsync([{ key, value: val }])
              setDirtyKeys((prev) => { const n = new Set(prev); n.delete(key); return n })
              addToast(val === 'true' ? 'Transcrição ativada' : 'Transcrição desativada', 'success')
            } catch {
              addToast('Falha ao salvar configuração', 'error')
            } finally {
              setSavingKeys((prev) => { const n = new Set(prev); n.delete(key); return n })
            }
          }}
          isSaving={savingKeys.has('audio_transcription_enabled')}
          isDirty={false}
        />
      </CollapsibleSection>

      {/* ── Health Check ─────────────────────────────────────────────────── */}
      <CollapsibleSection
        title="Health Check"
        subtitle="Validates credentials by calling external APIs"
        icon={
          <div className="p-2 rounded-lg bg-orange-50 border border-orange-100 shrink-0">
            <Activity className="w-4 h-4 text-orange-600" />
          </div>
        }
      >
        <HealthCheckCard />
      </CollapsibleSection>

      {/* ── Account ──────────────────────────────────────────────────────── */}
      <CollapsibleSection
        title="Account"
        subtitle="Telegram account linking"
        icon={
          <div className="p-2 rounded-lg bg-muted shrink-0">
            <Webhook className="w-4 h-4 text-muted-foreground" />
          </div>
        }
      >
        <p className="text-sm text-muted-foreground">
          To link your Telegram account to this web login, use:
        </p>
        <code className="mt-2 block text-xs bg-muted rounded-lg p-3 font-mono text-foreground">
          POST {apiUrl}/auth/link-telegram
        </code>
      </CollapsibleSection>

      <ToastContainer toasts={toasts} remove={removeToast} />
    </div>
  )
}

// ── Copy button helper ────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      }}
      className="p-2 rounded-lg border border-border hover:bg-muted transition-colors text-muted-foreground hover:text-foreground shrink-0"
      title="Copy"
    >
      {copied ? <Check className="w-4 h-4 text-green-600" /> : <Copy className="w-4 h-4" />}
    </button>
  )
}
