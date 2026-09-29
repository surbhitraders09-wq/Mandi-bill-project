import { Outlet } from 'react-router-dom'

import { CommandPalette } from '@/components/layout/command-palette'
import { Sidebar } from '@/components/layout/sidebar'
import { StatusBar } from '@/components/layout/status-bar'
import { TopBar } from '@/components/layout/top-bar'

export function AppShell() {
  return (
    <div className="flex h-screen flex-col bg-bg text-text">
      <TopBar />
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <main className="min-h-0 min-w-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
      <StatusBar />
      <CommandPalette />
    </div>
  )
}
