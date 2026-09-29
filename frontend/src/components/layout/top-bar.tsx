import { Bell, Menu, Search, User as UserIcon, LogOut } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Permission } from '@/components/layout/permission'
import { ThemeToggle } from '@/components/layout/theme-toggle'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

export function TopBar() {
  const navigate = useNavigate()
  const toggleSidebar = useUiStore((s) => s.toggleSidebar)
  const setCommandOpen = useUiStore((s) => s.setCommandOpen)
  const user = useAuthStore((s) => s.user)
  const clear = useAuthStore((s) => s.clear)
  const [notificationsOpen, setNotificationsOpen] = useState(false)

  const logout = () => {
    clear()
    navigate('/login')
  }

  return (
    <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-border bg-surface px-4">
      <Button variant="ghost" size="icon" onClick={toggleSidebar} aria-label="Toggle sidebar" className="md:hidden">
        <Menu className="h-4 w-4" />
      </Button>

      <button
        onClick={() => setCommandOpen(true)}
        className="flex h-9 w-full max-w-md items-center gap-2 rounded-md border border-border bg-bg px-3 text-sm text-muted transition-colors hover:border-info/50"
        aria-label="Global search (Ctrl+K)"
      >
        <Search className="h-4 w-4" />
        <span className="flex-1 text-left">Search…</span>
        <kbd className="hidden rounded border border-border bg-surface px-1.5 py-0.5 text-[10px] font-medium text-muted sm:inline">
          Ctrl K
        </kbd>
      </button>

      <div className="ml-auto flex items-center gap-1">
        <Permission permission="notifications:read">
          <div className="relative">
            <Button variant="ghost" size="icon" aria-label="Notifications" onClick={() => setNotificationsOpen((v) => !v)}>
              <Bell className="h-4 w-4" />
            </Button>
            {notificationsOpen && (
              <div className="absolute right-0 top-11 w-72 rounded-md border border-border bg-surface p-4 text-sm text-muted shadow-popover">
                <p className="font-medium text-text">Notifications</p>
                <p className="mt-1 text-xs">No new notifications.</p>
              </div>
            )}
          </div>
        </Permission>

        <ThemeToggle />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="User menu">
              <UserIcon className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel className="px-2 py-1.5">
              <p className="text-sm font-medium text-text">{user?.full_name ?? user?.username}</p>
              <p className="text-xs text-muted">{user?.role}</p>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => navigate('/settings')}>Settings</DropdownMenuItem>
            <DropdownMenuItem onClick={logout}>
              <LogOut className="h-4 w-4" />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
