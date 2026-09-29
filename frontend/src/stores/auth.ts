import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface SessionUser {
  id: number
  username: string
  full_name?: string
  role?: string
}

interface AuthState {
  user: SessionUser | null
  access_token: string | null
  refresh_token: string | null
  setSession: (s: Partial<AuthState>) => void
  clear: () => void
  getAccess: () => string | null
  getRefresh: () => string | null
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      access_token: null,
      refresh_token: null,
      setSession: (s) => set(s),
      clear: () => set({ user: null, access_token: null, refresh_token: null }),
      getAccess: () => get().access_token,
      getRefresh: () => get().refresh_token,
    }),
    { name: 'mandi-auth' },
  ),
)
