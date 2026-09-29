import { useEffect } from 'react'

import { useThemeStore } from '@/stores/theme'

export function ThemeProvider() {
  const theme = useThemeStore((s) => s.theme)
  const fontSize = useThemeStore((s) => s.fontSize)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  useEffect(() => {
    document.documentElement.dataset.fontSize = fontSize
  }, [fontSize])

  return null
}
