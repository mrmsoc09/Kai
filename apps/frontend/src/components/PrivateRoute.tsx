import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useStore } from '../store/system'

export default function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = useStore((s) => s.auth.token)
  const location = useLocation()
  if (!token) {
    return <Navigate to='/login' state={{ from: location }} replace />
  }
  return <>{children}</>
}
