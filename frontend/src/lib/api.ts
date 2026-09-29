import { useAuthStore } from '@/stores/auth'

export const BASE_URL = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export async function api<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const { getAccess, getRefresh, setSession, clear, user } = useAuthStore.getState()
  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')
  const token = getAccess()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let res = await fetch(`${BASE_URL}${path}`, { ...options, headers })

  if (res.status === 401 && token && path !== '/api/v1/auth/login') {
    const refresh = getRefresh()
    if (refresh) {
      const rr = await fetch(`${BASE_URL}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refresh }),
      })
      if (rr.ok) {
        const data = await rr.json()
        setSession({
          user: user,
          access_token: data.access_token,
          refresh_token: refresh,
        })
        const retryHeaders = new Headers(options.headers)
        retryHeaders.set('Content-Type', 'application/json')
        retryHeaders.set('Authorization', `Bearer ${data.access_token}`)
        res = await fetch(`${BASE_URL}${path}`, { ...options, headers: retryHeaders })
      } else {
        clear()
      }
    }
  }

  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as Record<string, unknown>
    const err = body as { error?: { message?: string }; detail?: string }
    throw new Error(err.error?.message ?? err.detail ?? `Request failed (${res.status})`)
  }
  return (await res.json()) as T
}
