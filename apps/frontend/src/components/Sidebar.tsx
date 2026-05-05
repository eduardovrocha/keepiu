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
} from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { api } from '../services/api'
import { cn } from '../utils/cn'

interface SidebarProps {
  onClose?: () => void
}

export function Sidebar({ onClose }: SidebarProps) {
  const storeLogout = useAuthStore((state) => state.logout)

  const logout = async () => {
    try {
      await api.post('/auth/logout')
    } finally {
      storeLogout()
    }
  }

  const navItems = [
    { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/library', icon: Library, label: 'Library' },
    { to: '/search', icon: Search, label: 'Search' },
    { to: '/processing', icon: Loader2, label: 'Processamento' },
    { to: '/workers', icon: Activity, label: 'Workers' },
    { to: '/settings', icon: Settings, label: 'Settings' },
  ]

  const handleNavClick = () => {
    onClose?.()
  }

  return (
    <aside className="w-64 h-full bg-card border-r border-border flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center flex-shrink-0">
            <Brain className="w-6 h-6 text-primary-foreground" />
          </div>
          <div>
            <h1 className="font-semibold text-lg text-foreground">Keepiu</h1>
            <p className="text-xs text-muted-foreground">Capture Everything</p>
          </div>
        </div>

        {/* Close button — visible on mobile only */}
        {onClose && (
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-muted transition-colors md:hidden"
            aria-label="Close menu"
          >
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={handleNavClick}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )
            }
          >
            <item.icon className="w-5 h-5" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-border">
        <button
          onClick={logout}
          className="flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors w-full"
        >
          <LogOut className="w-5 h-5" />
          Logout
        </button>
      </div>
    </aside>
  )
}
