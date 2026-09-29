import { useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api } from '@/lib/api'
import { toast } from '@/lib/toast'
import { useAuthStore } from '@/stores/auth'

interface LoginResponse {
  access_token: string
  refresh_token: string
  user?: { id: number; username: string; full_name?: string; role?: string }
}

export function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const setSession = useAuthStore((s) => s.setSession)
  const navigate = useNavigate()
  const location = useLocation()

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!username || !password) {
      toast.error('Enter username and password')
      return
    }
    setLoading(true)
    try {
      const data = await api<LoginResponse>('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      })
      setSession({
        user: data.user ?? { id: 0, username },
        access_token: data.access_token,
        refresh_token: data.refresh_token,
      })
      toast.success('Signed in')
      const from = (location.state as { from?: string } | null)?.from ?? '/dashboard'
      navigate(from, { replace: true })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl">e-Mandi ERP</CardTitle>
          <CardDescription>Sign in to the market office console</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </div>
            <Button type="submit" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
