export interface NavItem {
  label: string
  route: string
  permission: string
}

export interface NavGroup {
  label: string
  items: NavItem[]
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Overview',
    items: [{ label: 'Dashboard', route: '/dashboard', permission: 'dashboard:read' }],
  },
  {
    label: 'Farmers',
    items: [
      { label: 'Registration', route: '/farmers', permission: 'farmers:read' },
      { label: 'Payments', route: '/farmers/payments', permission: 'payments:read' },
    ],
  },
  {
    label: 'Traders',
    items: [
      { label: 'Registration', route: '/traders', permission: 'traders:read' },
      { label: 'Stock', route: '/traders/stock', permission: 'stock:read' },
    ],
  },
  {
    label: 'Operations',
    items: [
      { label: 'Stock', route: '/stock', permission: 'stock:read' },
      { label: 'Payments', route: '/payments', permission: 'payments:read' },
      { label: 'Bills', route: '/bills', permission: 'bills:read' },
      { label: 'Reports', route: '/reports', permission: 'reports:read' },
    ],
  },
  {
    label: 'Documents',
    items: [{ label: 'Document Center', route: '/documents', permission: 'documents:read' }],
  },
  {
    label: 'System',
    items: [
      { label: 'Automation', route: '/automation', permission: 'automation:read' },
      { label: 'Notifications', route: '/notifications', permission: 'notifications:read' },
      { label: 'Activity Log', route: '/audit', permission: 'audit:read' },
      { label: 'Settings', route: '/settings', permission: 'settings:read' },
    ],
  },
]

export const PERMISSIONS: Record<string, string[]> = {
  administrator: ['*'],
  operator: [
    'bills:*', 'payments:*', 'automation:*', 'search:read', 'dashboard:read', 'stock:read',
    'farmers:read', 'farmers:write', 'traders:read', 'traders:write',
    'masterdata:read', 'masterdata:write',
  ],
  accountant: [
    'bills:read', 'payments:*', 'reports:read', 'search:read', 'dashboard:read',
    'settings:read', 'audit:read', 'farmers:read', 'traders:read', 'masterdata:read',
  ],
  inspector: [
    'search:read', 'dashboard:read', 'bills:read', 'payments:read', 'reports:read',
    'audit:read', 'stock:read', 'notifications:read', 'settings:read',
    'farmers:read', 'traders:read', 'masterdata:read',
  ],
}

export function hasPermission(role: string | undefined, permission: string): boolean {
  if (!role) return false
  const perms = PERMISSIONS[role] ?? []
  if (perms.includes('*')) return true
  if (perms.includes(permission)) return true
  return perms.includes(`${permission.split(':')[0]}:*`)
}
