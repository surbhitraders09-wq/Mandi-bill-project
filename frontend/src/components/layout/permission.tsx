import type { ReactNode } from 'react'

import { hasPermission } from '@/constants'
import { useAuthStore } from '@/stores/auth'

interface PermissionProps {
  permission: string
  children: ReactNode
  fallback?: ReactNode
}

export function Permission({ permission, children, fallback = null }: PermissionProps) {
  const role = useAuthStore((s) => s.user?.role)
  if (!hasPermission(role, permission)) return <>{fallback}</>
  return <>{children}</>
}
