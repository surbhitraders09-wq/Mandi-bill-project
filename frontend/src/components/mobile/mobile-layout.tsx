import type { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'

import { cn } from '@/lib/utils'

export function MobileLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-bg text-text">
      <div className="mx-auto w-full max-w-md px-4 pb-20 pt-6">{children}</div>
      <MobileTabBar />
    </div>
  )
}

const TABS = [
  { to: '/mobile', label: 'बिल', icon: <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /> },
  { to: '/mobile/summary', label: 'सारांश', icon: <path d="M3 3v18h18" /> },
  { to: '/mobile/reports', label: 'रिपोर्ट', icon: <path d="M9 17H7A5 5 0 0 1 7 7h2M9 17h6M9 17V7m6 10V7m-3 0h.01M12 7h.01M15 10h.01" /> },
]

function MobileTabBar() {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-bg/95 backdrop-blur">
      <div className="mx-auto flex max-w-md">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.to === '/mobile'}
            className={({ isActive }) =>
              cn(
                'flex flex-1 flex-col items-center gap-1 py-2.5 text-[11px] font-medium transition-colors',
                isActive ? 'text-primary' : 'text-muted hover:text-text',
              )
            }
          >
            {() => (
              <>
                <svg
                  width="22"
                  height="22"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  {tab.icon}
                </svg>
                <span>{tab.label}</span>
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  )
}

export function MobileHeader({ title, onBack, hideSettings }: { title: string; onBack?: () => void; hideSettings?: boolean }) {
  const navigate = useNavigate()
  return (
    <header className="sticky top-0 z-10 -mx-4 mb-4 border-b border-border bg-bg/95 px-4 py-3 backdrop-blur">
      <div className="flex items-center gap-3">
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="flex h-9 w-9 items-center justify-center rounded-md text-muted transition-colors hover:bg-border/60 active:bg-border"
            aria-label="वापस जाएँ"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 12H5" />
              <path d="m12 19-7-7 7-7" />
            </svg>
          </button>
        )}
        <h1 className="flex-1 text-base font-semibold">{title}</h1>
        {!hideSettings && (
          <button
            type="button"
            onClick={() => navigate('/mobile/settings')}
            className="flex h-9 w-9 items-center justify-center rounded-md text-muted transition-colors hover:bg-border/60 active:bg-border"
            aria-label="सेटिंग्स"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </button>
        )}
      </div>
    </header>
  )
}
