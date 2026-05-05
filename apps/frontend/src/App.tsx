import { useEffect, useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import { api } from './services/api'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Layout } from './components/Layout'
import { Login } from './pages/Login'
import { Dashboard } from './pages/Dashboard'
import { Library } from './pages/Library'
import { ContentDetail } from './pages/ContentDetail'
import { Search } from './pages/Search'
import { Settings } from './pages/Settings'
import { Processing } from './pages/Processing'
import { Workers } from './pages/Workers'
import { LoadingSpinner } from './components/LoadingSpinner'

function App() {
  const { isAuthenticated, login, logout } = useAuthStore()
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    api.get('/auth/me')
      .then((res) => login(res.data?.is_admin ?? false))
      .catch(() => logout())
      .finally(() => setChecking(false))
  }, [])

  if (checking) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <LoadingSpinner />
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <ErrorBoundary>
        <Login />
      </ErrorBoundary>
    )
  }

  return (
    <ErrorBoundary>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/library" element={<Library />} />
          <Route path="/content/:id" element={<ContentDetail />} />
          <Route path="/search" element={<Search />} />
          <Route path="/processing" element={<Processing />} />
          <Route path="/workers" element={<Workers />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Layout>
    </ErrorBoundary>
  )
}

export default App
