import { create } from 'zustand'

interface UiState {
  sidebarCollapsed: boolean
  commandOpen: boolean
  setSidebarCollapsed: (v: boolean) => void
  toggleSidebar: () => void
  setCommandOpen: (v: boolean) => void
}

export const useUiStore = create<UiState>()((set) => ({
  sidebarCollapsed: false,
  commandOpen: false,
  setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setCommandOpen: (commandOpen) => set({ commandOpen }),
}))
