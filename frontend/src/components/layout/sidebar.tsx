import { Link, useLocation } from 'react-router-dom'

import { hasPermission, NAV_GROUPS } from '@/constants'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { cn } from '@/lib/utils'

export function Sidebar() {
  const location = useLocation()
  const collapsed = useUiStore((s) => s.sidebarCollapsed)
  const role = useAuthStore((s) => s.user?.role)

  return (
    <aside
      className={cn(
        'sticky top-14 hidden h-[calc(100vh-3.5rem)] shrink-0 overflow-y-auto border-r border-border bg-surface md:block',
        collapsed ? 'w-16' : 'w-60',
      )}
    >
      <nav className="flex flex-col gap-4 p-3" aria-label="Main navigation">
        {NAV_GROUPS.map((group) => {
          const visible = group.items.filter((i) => hasPermission(role, i.permission))
          if (visible.length === 0) return null
          return (
            <div key={group.label}>
              {!collapsed && (
                <p className="mb-1 px-2 text-[11px] font-semibold uppercase tracking-wider text-muted">
                  {group.label}
                </p>
              )}
              <ul className="flex flex-col gap-0.5">
                {visible.map((item) => {
                  const active = location.pathname === item.route
                  return (
                    <li key={item.route}>
                      <Link
                        to={item.route}
                        title={collapsed ? item.label : undefined}
                        className={cn(
                          'flex h-9 items-center rounded-md px-2 text-sm font-medium transition-colors',
                          collapsed && 'justify-center',
                          active ? 'bg-primary/10 text-primary' : 'text-muted hover:bg-muted/10 hover:text-text',
                        )}
                      >
                        {collapsed ? <span className="truncate">{item.label.charAt(0)}</span> : item.label}
                      </Link>
                    </li>
                  )
                })}
              </ul>
            </div>
          )
        })}
      </nav>
    </aside>
  )
}
