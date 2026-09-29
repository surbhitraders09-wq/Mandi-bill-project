import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { useAuthStore } from '@/stores/auth'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const user = useAuthStore((s) => s.user)
  const location = useLocation()
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <>{children}</>
}
