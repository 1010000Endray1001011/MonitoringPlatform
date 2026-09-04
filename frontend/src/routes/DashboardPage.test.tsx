import { Route, Routes } from 'react-router-dom'
import { HttpResponse, http } from 'msw'
import { fireEvent, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { server } from '../api/mocks/server'
import { renderWithProviders } from '../test/renderWithProviders'
import { useAuthStore } from '../auth/store'
import type { MonitorList, PaginatedMonitorList } from '../api/types'
import { DashboardPage } from './DashboardPage'

const BASE = 'http://localhost:8000'

function makeMonitor(overrides: Partial<MonitorList> = {}): MonitorList {
  return {
    id: 'aaaaaaaa-0000-0000-0000-000000000001',
    name: 'Prod API',
    url: 'https://example.com/health',
    method: 'GET',
    expected_status: 200,
    interval_seconds: 300,
    timeout_seconds: 10,
    is_enabled: true,
    status: 'UP',
    last_checked_at: '2026-09-03T10:00:00Z',
    last_response_time_ms: 120,
    open_incident_id: null,
    next_check_at: '2026-09-03T10:05:00Z',
    created_at: '2026-09-01T00:00:00Z',
    ...overrides,
  }
}

function paginated(results: MonitorList[]): PaginatedMonitorList {
  return { count: results.length, next: null, previous: null, results }
}

function renderDashboard() {
  return renderWithProviders(
    <Routes>
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/login" element={<div>Login placeholder</div>} />
      <Route path="/monitors/:id" element={<div>Detail placeholder</div>} />
    </Routes>,
    { route: '/dashboard' },
  )
}

beforeEach(() => {
  useAuthStore.getState().setAccessToken('test-token')
})

describe('DashboardPage', () => {
  it('renders the monitor list from the server', async () => {
    server.use(
      http.get(`${BASE}/api/v1/monitors/`, () =>
        HttpResponse.json(paginated([makeMonitor({ name: 'Prod API' })])),
      ),
    )

    renderDashboard()

    expect(await screen.findByText('Prod API')).toBeInTheDocument()
    expect(screen.getByText('UP')).toBeInTheDocument()
  })

  it('shows the first-monitor empty state when there are none and no search is active', async () => {
    server.use(http.get(`${BASE}/api/v1/monitors/`, () => HttpResponse.json(paginated([]))))

    renderDashboard()

    expect(await screen.findByText(/don't have any monitors yet/i)).toBeInTheDocument()
  })

  it('navigates to the monitor detail route when a card is opened', async () => {
    server.use(
      http.get(`${BASE}/api/v1/monitors/`, () => HttpResponse.json(paginated([makeMonitor()]))),
    )
    renderDashboard()
    await screen.findByText('Prod API')

    fireEvent.click(screen.getByRole('button', { name: 'Details' }))

    expect(await screen.findByText('Detail placeholder')).toBeInTheDocument()
  })

  it('creates a monitor and returns to the list, which now includes it', async () => {
    let created = false
    server.use(
      http.get(`${BASE}/api/v1/monitors/`, () =>
        HttpResponse.json(paginated(created ? [makeMonitor({ name: 'New Site' })] : [])),
      ),
      http.post(`${BASE}/api/v1/monitors/`, async ({ request }) => {
        created = true
        const body = (await request.json()) as { name: string }
        return HttpResponse.json({ ...makeMonitor({ name: body.name }) }, { status: 201 })
      }),
    )
    renderDashboard()
    await screen.findByText(/don't have any monitors yet/i)

    fireEvent.click(screen.getByRole('button', { name: 'New monitor' }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'New Site' } })
    fireEvent.change(screen.getByLabelText('URL'), {
      target: { value: 'https://newsite.example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create monitor' }))

    expect(await screen.findByText('New Site')).toBeInTheDocument()
  })

  it('shows a quota message on a 422 without closing the form', async () => {
    server.use(
      http.get(`${BASE}/api/v1/monitors/`, () => HttpResponse.json(paginated([]))),
      http.post(`${BASE}/api/v1/monitors/`, () =>
        HttpResponse.json(
          { error: { code: 'quota_exceeded', message: 'Quota exceeded.', details: null } },
          { status: 422 },
        ),
      ),
    )
    renderDashboard()
    await screen.findByText(/don't have any monitors yet/i)
    fireEvent.click(screen.getByRole('button', { name: 'New monitor' }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'One Too Many' } })
    fireEvent.change(screen.getByLabelText('URL'), { target: { value: 'https://x.example.com' } })

    fireEvent.click(screen.getByRole('button', { name: 'Create monitor' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/quota/i)
    // Still on the form, not silently dropped back to the list.
    expect(screen.getByRole('button', { name: 'Create monitor' })).toBeInTheDocument()
  })

  it('shows the field-level error on a 400 validation failure', async () => {
    server.use(
      http.get(`${BASE}/api/v1/monitors/`, () => HttpResponse.json(paginated([]))),
      http.post(`${BASE}/api/v1/monitors/`, () =>
        HttpResponse.json(
          {
            error: {
              code: 'validation_error',
              message: 'Validation failed.',
              details: { url: ['Hostname is not allowed.'] },
            },
          },
          { status: 400 },
        ),
      ),
    )
    renderDashboard()
    await screen.findByText(/don't have any monitors yet/i)
    fireEvent.click(screen.getByRole('button', { name: 'New monitor' }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Bad Target' } })
    fireEvent.change(screen.getByLabelText('URL'), { target: { value: 'http://127.0.0.1/' } })

    fireEvent.click(screen.getByRole('button', { name: 'Create monitor' }))

    expect(await screen.findByText('Hostname is not allowed.')).toBeInTheDocument()
  })

  it('optimistically shows PAUSED as soon as pause is clicked', async () => {
    // The GET handler reflects the pause too (not just the POST) — the
    // mutation's onSettled triggers a real refetch right after the optimistic
    // patch, and a GET mock that always answered "still UP" would silently
    // overwrite the optimistic value back, making this test pass or fail by
    // accident depending on timing rather than on what the component does.
    let paused = false
    server.use(
      http.get(`${BASE}/api/v1/monitors/`, () =>
        HttpResponse.json(
          paginated([makeMonitor(paused ? { status: 'PAUSED', is_enabled: false } : {})]),
        ),
      ),
      http.post(`${BASE}/api/v1/monitors/:id/pause/`, () => {
        paused = true
        return HttpResponse.json({ id: makeMonitor().id, status: 'PAUSED', is_enabled: false })
      }),
    )
    renderDashboard()
    const card = (await screen.findByText('Prod API')).closest('fieldset') as HTMLElement

    fireEvent.click(within(card).getByRole('button', { name: 'Pause' }))

    // Optimistic update lands before the mocked network response even
    // needs to resolve — this is checking the instant, client-side flip,
    // not the eventual server-confirmed state.
    expect(await within(card).findByText('PAUSED')).toBeInTheDocument()
  })
})
