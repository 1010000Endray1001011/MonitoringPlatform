import { type FormEvent, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Button, TextInput } from 'react95'
import { apiClient, ApiError } from '../api/client'
import type { AccessToken } from '../api/types'
import { useAuthStore } from '../auth/store'
import { AuthForm, AuthMessage, AuthWindow } from '../components/AuthWindow'

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const justRegistered = Boolean(
    (location.state as { justRegistered?: boolean } | null)?.justRegistered,
  )
  const setAccessToken = useAuthStore((state) => state.setAccessToken)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const login = useMutation({
    mutationFn: () => apiClient.post<AccessToken>('/api/v1/auth/token', { email, password }),
    onSuccess: (data) => {
      setAccessToken(data.access)
      navigate('/dashboard', { replace: true })
    },
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    login.mutate()
  }

  return (
    <AuthWindow active="login">
      {/* Both messages sit inside the form rather than above it purely so
          the form's own gap spaces them — a sibling of the form would
          need spacing rules of its own to avoid butting against the first
          input. */}
      <AuthForm onSubmit={handleSubmit}>
        {justRegistered && <AuthMessage $tone="info">Account created — log in below.</AuthMessage>}
        <TextInput
          name="email"
          type="email"
          placeholder="Email"
          fullWidth
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
        <TextInput
          name="password"
          type="password"
          placeholder="Password"
          fullWidth
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
        {login.isError && (
          <AuthMessage $tone="error" role="alert">
            {describeLoginError(login.error)}
          </AuthMessage>
        )}
        <Button type="submit" fullWidth disabled={login.isPending}>
          {login.isPending ? 'Logging in…' : 'Log in'}
        </Button>
      </AuthForm>
    </AuthWindow>
  )
}

function describeLoginError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Incorrect email or password.'
    if (error.status === 429) return 'Too many attempts — try again in a minute.'
  }
  return 'Something went wrong. Please try again.'
}
