import { create } from 'zustand'

export type ToastKind = 'success' | 'error' | 'info' | 'warning'

export interface ToastItem {
  id: number
  title: string
  description?: string
  kind: ToastKind
}

interface ToastState {
  toasts: ToastItem[]
  push: (t: Omit<ToastItem, 'id'>) => void
  dismiss: (id: number) => void
}

export const useToastStore = create<ToastState>()((set) => ({
  toasts: [],
  push: (t) =>
    set((s) => ({
      toasts: [...s.toasts, { ...t, id: Date.now() + Math.random() * 1000 }],
    })),
  dismiss: (id) =>
    set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) })),
}))

export function toast(t: Omit<ToastItem, 'id'>) {
  useToastStore.getState().push(t)
}

toast.success = (title: string, description?: string) => toast({ kind: 'success', title, description })
toast.error = (title: string, description?: string) => toast({ kind: 'error', title, description })
toast.info = (title: string, description?: string) => toast({ kind: 'info', title, description })
toast.warning = (title: string, description?: string) => toast({ kind: 'warning', title, description })
