import { useState, useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Library,
  Search,
  Settings,
  LogOut,
  Brain,
  X,
  Loader2,
  Activity,
  Sun,
  Moon,
  Info,
} from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { api } from '../services/api'
import { cn } from '../utils/cn'

interface SidebarProps {
  onClose?: () => void
}

function useTheme() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light')

  useEffect(() => {
    setTheme(document.documentElement.classList.contains('dark') ? 'dark' : 'light')
  }, [])

  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.classList.toggle('dark', next === 'dark')
    localStorage.setItem('keepiu-theme', next)
    setTheme(next)
  }

  return { theme, toggle }
}

export function Sidebar({ onClose }: SidebarProps) {
  const storeLogout = useAuthStore((state) => state.logout)
  const { theme, toggle } = useTheme()

  const logout = async () => {
    try {
      await api.post('/auth/logout')
    } finally {
      storeLogout()
    }
  }

  const navItems = [
    { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/library',   icon: Library,         label: 'Library' },
    { to: '/search',    icon: Search,           label: 'Search' },
    { to: '/processing', icon: Loader2,         label: 'Processing' },
    { to: '/workers',   icon: Activity,         label: 'Workers' },
    { to: '/settings',  icon: Settings,         label: 'Settings' },
    { to: '/about',     icon: Info,             label: 'Sobre' },
  ]

  return (
    <aside className="w-60 h-full bg-card border-r border-border flex flex-col">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center flex-shrink-0">
            <Brain className="w-4 h-4 text-primary-foreground" />
          </div>
          <span className="font-semibold text-base text-foreground tracking-tight">Keepiu</span>
        </div>

        <div className="flex items-center gap-1">
          {/* Theme toggle */}
          <button
            onClick={toggle}
            aria-label="Toggle theme"
            className="p-1.5 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          >
            {theme === 'dark' ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
          </button>

          {/* Mobile close */}
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-muted transition-colors md:hidden"
              aria-label="Close menu"
            >
              <X className="w-3.5 h-3.5 text-muted-foreground" />
            </button>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onClose}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )
            }
          >
            <item.icon className="w-4 h-4 flex-shrink-0" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-3 py-4 border-t border-border">
        <button
          onClick={logout}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors w-full"
        >
          <LogOut className="w-4 h-4 flex-shrink-0" />
          Logout
        </button>
      </div>
    </aside>
  )
}
