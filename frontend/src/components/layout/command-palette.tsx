import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Command } from 'cmdk'
import { FileText, Loader2, Search } from 'lucide-react'

import { hasPermission, NAV_GROUPS } from '@/constants'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

interface SearchHit {
  type: string
  id: number
  title: string
  subtitle?: string
  route: string
}

export function CommandPalette() {
  const open = useUiStore((s) => s.commandOpen)
  const setOpen = useUiStore((s) => s.setCommandOpen)
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<SearchHit[]>([])
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const role = useAuthStore((s) => s.user?.role)

  const close = useCallback(() => setOpen(false), [setOpen])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen(!useUiStore.getState().commandOpen)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setOpen])

  useEffect(() => {
    if (!open) {
      setQuery('')
      setHits([])
      return
    }
  }, [open])

  useEffect(() => {
    if (!open || query.trim().length === 0) {
      setHits([])
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    const t = setTimeout(async () => {
      try {
        const data = await api<{ items: SearchHit[] }>(`/api/v1/search?q=${encodeURIComponent(query.trim())}`)
        if (!cancelled) setHits(data.items ?? [])
      } catch {
        if (!cancelled) setHits([])
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(t)
    }
  }, [open, query])

  const navItems = NAV_GROUPS.flatMap((g) =>
    g.items
      .filter((i) => hasPermission(role, i.permission))
      .map((i) => ({ ...i, group: g.label })),
  )

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Global search"
      className="fixed left-1/2 top-[15%] z-[70] w-[min(620px,90vw)] -translate-x-1/2 overflow-hidden rounded-lg border border-border bg-surface shadow-popover"
      overlayClassName="fixed inset-0 z-[65] bg-black/40"
    >
      <div className="flex items-center gap-2 border-b border-border px-3">
        <Search className="h-4 w-4 shrink-0 text-muted" />
        <Command.Input
          value={query}
          onValueChange={setQuery}
          placeholder="Search bills, farmers, traders, pages… (press ESC to close)"
          className="h-12 w-full bg-transparent text-sm text-text outline-none placeholder:text-muted"
        />
        {loading && <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted" />}
      </div>
      <Command.List className="max-h-[320px] overflow-y-auto p-2">
        <Command.Empty className="px-3 py-6 text-center text-sm text-muted">No results found</Command.Empty>

        {hits.length > 0 && (
          <>
            <Command.Group heading="Records">
              {hits.map((h) => (
                <Command.Item
                  key={`${h.type}-${h.id}`}
                  value={h.title}
                  onSelect={() => {
                    close()
                    navigate(h.route)
                  }}
                  className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-text data-[selected=true]:bg-muted/10"
                >
                  <FileText className="h-4 w-4 text-muted" />
                  <div className="flex-1">
                    <p className="font-medium">{h.title}</p>
                    {h.subtitle && <p className="text-xs text-muted">{h.subtitle}</p>}
                  </div>
                </Command.Item>
              ))}
            </Command.Group>
          </>
        )}

        {navItems.length > 0 && (
          <Command.Group heading="Pages">
            {navItems.map((i) => (
              <Command.Item
                key={i.route}
                value={`${i.group} ${i.label}`}
                onSelect={() => {
                  close()
                  navigate(i.route)
                }}
                className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-text data-[selected=true]:bg-muted/10"
              >
                <span className="text-xs text-muted">{i.group}</span>
                <span className="flex-1">{i.label}</span>
              </Command.Item>
            ))}
          </Command.Group>
        )}
      </Command.List>
    </Command.Dialog>
  )
}
