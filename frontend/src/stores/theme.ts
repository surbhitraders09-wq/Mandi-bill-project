import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ThemeMode = 'light' | 'dark' | 'high-contrast'
export type FontSize = 'normal' | 'large'

interface ThemeState {
  theme: ThemeMode
  fontSize: FontSize
  setTheme: (t: ThemeMode) => void
  setFontSize: (f: FontSize) => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      theme: 'light',
      fontSize: 'normal',
      setTheme: (theme) => set({ theme }),
      setFontSize: (fontSize) => set({ fontSize }),
    }),
    { name: 'mandi-theme' },
  ),
)
