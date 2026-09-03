import { Route, Routes } from 'react-router-dom'
import { HttpResponse, http } from 'msw'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { server } from '../api/mocks/server'
import { renderWithProviders } from '../test/renderWithProviders'
import { useAuthStore } from '../auth/store'
import { LoginPage } from './LoginPage'

const BASE = 'http://localhost:8000'

function renderLoginRoute() {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/dashboard" element={<div>Dashboard placeholder</div>} />
    </Routes>,
    { route: '/login' },
  )
}

function fillAndSubmit(email: string, password: string) {
  fireEvent.change(screen.getByPlaceholderText('Email'), { target: { value: email } })
  fireEvent.change(screen.getByPlaceholderText('Password'), { target: { value: password } })
  fireEvent.click(screen.getByRole('button', { name: /log in/i }))
}

describe('LoginPage', () => {
  it('stores the access token and navigates to the dashboard on success', async () => {
    server.use(
      http.post(`${BASE}/api/v1/auth/token`, () => HttpResponse.json({ access: 'issued-token' })),
    )
    renderLoginRoute()

    fillAndSubmit('dev@example.com', 'S0me-Str0ng-Pass')

    await waitFor(() => expect(screen.getByText('Dashboard placeholder')).toBeInTheDocument())
    expect(useAuthStore.getState().accessToken).toBe('issued-token')
  })

  it('shows a readable message on invalid credentials, without navigating', async () => {
    server.use(
      http.post(`${BASE}/api/v1/auth/token`, () => HttpResponse.json({}, { status: 401 })),
    )
    renderLoginRoute()

    fillAndSubmit('dev@example.com', 'wrong-password')

    expect(await screen.findByRole('alert')).toHaveTextContent(/incorrect email or password/i)
    expect(screen.queryByText('Dashboard placeholder')).not.toBeInTheDocument()
  })
})
