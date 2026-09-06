import { type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Button, TextInput } from 'react95'
import { apiClient, ApiError } from '../api/client'
import type { RegisterResponse } from '../api/types'
import { AuthForm, AuthMessage, AuthWindow } from '../components/AuthWindow'

export function RegisterPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')

  const register = useMutation({
    mutationFn: () =>
      apiClient.post<RegisterResponse>('/api/v1/auth/register', {
        email,
        password,
        password_confirm: passwordConfirm,
      }),
    onSuccess: () => {
      // Registration doesn't return tokens (see the backend contract) —
      // logging in is a deliberate separate step, not auto-chained here.
      navigate('/login', { state: { justRegistered: true } })
    },
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    register.mutate()
  }

  return (
    <AuthWindow active="register">
      <AuthForm onSubmit={handleSubmit}>
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
        <TextInput
          name="password_confirm"
          type="password"
          placeholder="Confirm password"
          fullWidth
          value={passwordConfirm}
          onChange={(event) => setPasswordConfirm(event.target.value)}
          required
        />
        {register.isError && (
          <AuthMessage $tone="error" role="alert">
            {describeRegisterError(register.error)}
          </AuthMessage>
        )}
        <Button type="submit" fullWidth disabled={register.isPending}>
          {register.isPending ? 'Creating account…' : 'Register'}
        </Button>
      </AuthForm>
    </AuthWindow>
  )
}

function describeRegisterError(error: unknown): string {
  if (error instanceof ApiError && error.status === 400) {
    const details = (error.body as { error?: { details?: Record<string, string[]> } })?.error
      ?.details
    const firstMessage = details && Object.values(details).flat()[0]
    if (typeof firstMessage === 'string') return firstMessage
    return 'Please check your details and try again.'
  }
  return 'Something went wrong. Please try again.'
}
