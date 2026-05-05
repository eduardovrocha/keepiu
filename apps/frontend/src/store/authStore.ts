import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthState {
  isAuthenticated: boolean
  isAdmin: boolean
  login: (isAdmin?: boolean) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      isAuthenticated: false,
      isAdmin: false,
      login: (isAdmin = false) => set({ isAuthenticated: true, isAdmin }),
      logout: () => set({ isAuthenticated: false, isAdmin: false }),
    }),
    {
      name: 'sv-auth',
      partialize: (s) => ({ isAuthenticated: s.isAuthenticated, isAdmin: s.isAdmin }),
    }
  )
)
