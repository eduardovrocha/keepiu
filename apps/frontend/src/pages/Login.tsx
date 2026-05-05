import { useState, useEffect } from 'react'
import { Brain, Eye, EyeOff } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { login } from '../services/contentApi'
import { api } from '../services/api'
import { Card } from '../components/Card'
import { cn } from '../utils/cn'

export function Login() {
  const [mode, setMode] = useState<'multi_user' | 'single_user' | null>(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const loginStore = useAuthStore((state) => state.login)

  useEffect(() => {
    api.get('/auth/config').then((r) => setMode(r.data.mode ?? 'multi_user')).catch(() => setMode('multi_user'))
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)
    try {
      const effectiveUsername = mode === 'single_user' ? 'owner' : username
      const data = await login(effectiveUsername, password)
      loginStore(data?.is_admin ?? false)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Invalid credentials')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-primary flex items-center justify-center mb-4">
            <Brain className="w-8 h-8 text-primary-foreground" />
          </div>
          <h1 className="text-2xl font-bold text-foreground">Keepiu</h1>
          <p className="text-muted-foreground mt-1">Capture Everything</p>
        </div>

        <Card className="p-8">
          <h2 className="text-xl font-semibold text-foreground mb-6">Sign In</h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode !== 'single_user' && (
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">
                  Username
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className={cn(
                    'w-full px-3 py-2 rounded-lg border bg-background text-sm',
                    'focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary',
                    'transition-colors'
                  )}
                  placeholder="admin"
                  required={mode !== 'single_user'}
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-foreground mb-1.5">
                {mode === 'single_user' ? 'Senha de acesso' : 'Password'}
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={cn(
                    'w-full px-3 py-2 rounded-lg border bg-background text-sm pr-10',
                    'focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary',
                    'transition-colors'
                  )}
                  placeholder="••••••••"
                  autoFocus={mode === 'single_user'}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="rounded-lg bg-destructive/5 border border-destructive/30 p-3 text-sm text-destructive">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading || mode === null}
              className={cn(
                'w-full py-2.5 px-4 rounded-lg bg-primary text-primary-foreground font-medium',
                'hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary/20',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                'transition-colors'
              )}
            >
              {isLoading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>

          {mode !== 'single_user' && (
            <div className="mt-6 pt-6 border-t border-border">
              <p className="text-xs text-muted-foreground text-center">
                Don't have an account?{' '}
                <a href="/register" className="text-primary hover:underline">
                  Create one
                </a>
              </p>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
