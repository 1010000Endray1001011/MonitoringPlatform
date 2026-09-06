import { Route, Routes } from 'react-router-dom'
import { HttpResponse, http } from 'msw'
import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { server } from '../api/mocks/server'
import { renderWithProviders } from '../test/renderWithProviders'
import { useAuthStore } from '../auth/store'
import { ProtectedRoute } from './ProtectedRoute'

const BASE = 'http://localhost:8000'

function renderProtectedRoute() {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<div>Login placeholder</div>} />
      <Route element={<ProtectedRoute />}>
        <Route path="/dashboard" element={<div>Dashboard placeholder</div>} />
      </Route>
    </Routes>,
    { route: '/dashboard' },
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    useAuthStore.getState().clearAccessToken()
  })

  it('renders the protected content immediately when a token is already in memory', async () => {
    useAuthStore.getState().setAccessToken('already-have-one')
    renderProtectedRoute()

    expect(await screen.findByText('Dashboard placeholder')).toBeInTheDocument()
  })

  it('silently refreshes and renders the protected content when the cookie is still valid', async () => {
    server.use(
      http.post(`${BASE}/api/v1/auth/token/refresh`, () =>
        HttpResponse.json({ access: 'refreshed-token' }),
      ),
    )
    renderProtectedRoute()

    expect(await screen.findByText('Dashboard placeholder')).toBeInTheDocument()
    expect(useAuthStore.getState().accessToken).toBe('refreshed-token')
  })

  it('redirects to /login when there is no valid session at all', async () => {
    server.use(
      http.post(`${BASE}/api/v1/auth/token/refresh`, () => HttpResponse.json({}, { status: 401 })),
    )
    renderProtectedRoute()

    await waitFor(() => expect(screen.getByText('Login placeholder')).toBeInTheDocument())
  })

  it('ends up at /login rather than hanging when the backend is unreachable', async () => {
    // HttpResponse.error() simulates the fetch() promise itself rejecting
    // (network down, CORS failure) rather than resolving with a bad status
    // — the failure mode useAuthBootstrap's refreshAccessToken().catch()
    // exists for.
    server.use(http.post(`${BASE}/api/v1/auth/token/refresh`, () => HttpResponse.error()))
    renderProtectedRoute()

    await waitFor(() => expect(screen.getByText('Login placeholder')).toBeInTheDocument())
  })
})
