import React, { useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useStore } from '../store/system'
import { clearCsrfToken } from '../lib/api'

export default function PrivateRoute({ children }: { children: React.ReactNode }) {
  const auth = useStore((s) => s.auth)
  const bootstrapSession = useStore((s) => s.bootstrapSession)
  const markAuthChecked = useStore((s) => s.markAuthChecked)
  const logout = useStore((s) => s.logout)
  const location = useLocation()

  useEffect(() => {
    if (auth.checked) return
    let active = true
    const bootstrap = async () => {
      try {
        const response = await fetch('/auth/me', {
          method: 'GET',
          credentials: 'include',
          cache: 'no-store',
        })
        if (!active) return
        if (response.ok) {
          const user = await response.json()
          if (!active) return
          bootstrapSession({
            id: String(user?.id ?? 'session-user'),
            roles: Array.isArray(user?.roles) ? user.roles : [],
            tenant_id: user?.tenant_id ? String(user.tenant_id) : undefined,
          })
          return
        }
      } catch {
        // noop: handled by fallback branch below
      }
      if (!active) return
      clearCsrfToken()
      logout()
      markAuthChecked()
    }
    void bootstrap()
    return () => {
      active = false
    }
  }, [auth.checked, bootstrapSession, logout, markAuthChecked])

  if (!auth.checked) {
    return null
  }

  if (!auth.authenticated) {
    return <Navigate to='/login' state={{ from: location }} replace />
  }
  return <>{children}</>
}
