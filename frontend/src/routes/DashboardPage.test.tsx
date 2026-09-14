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
  // CreateMonitorForm's channel multiselect fetches this unconditionally
  // once the form mounts — an empty default here keeps every test that
  // doesn't care about channels from having to know that.
  server.use(
    http.get(`${BASE}/api/v1/notification-channels/`, () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
  )
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

  it('submits typed values for expected status and timeout, not the defaults', async () => {
    // Regression test: react95's NumberInput only calls onChange from its
    // increment/decrement buttons — for a controlled instance (value +
    // onChange), typing into the field does nothing at all, because its
    // internal useControlledOrUncontrolled hook makes the typed-input
    // handler a no-op. Found live in the browser (typing "404" left the
    // field showing "200"); fixed by switching both fields to
    // TextInput type="number". This test is what should have caught it.
    let submittedBody:
      | {
          expected_status?: number
          timeout_seconds?: number
          failure_threshold?: number
          success_threshold?: number
        }
      | undefined
    let created = false
    server.use(
      http.get(`${BASE}/api/v1/monitors/`, () =>
        HttpResponse.json(paginated(created ? [makeMonitor({ name: 'New Site' })] : [])),
      ),
      http.post(`${BASE}/api/v1/monitors/`, async ({ request }) => {
        submittedBody = (await request.json()) as {
          expected_status?: number
          timeout_seconds?: number
          failure_threshold?: number
          success_threshold?: number
        }
        created = true
        return HttpResponse.json(makeMonitor({ name: 'New Site' }), { status: 201 })
      }),
    )
    renderDashboard()
    await screen.findByText(/don't have any monitors yet/i)

    fireEvent.click(screen.getByRole('button', { name: 'New monitor' }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'New Site' } })
    fireEvent.change(screen.getByLabelText('URL'), {
      target: { value: 'https://newsite.example.com' },
    })
    fireEvent.change(screen.getByLabelText('Expected status code'), {
      target: { value: '404' },
    })
    fireEvent.change(screen.getByLabelText('Timeout (seconds)'), { target: { value: '25' } })
    fireEvent.change(screen.getByLabelText('Failure threshold'), { target: { value: '1' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create monitor' }))

    await screen.findByText('New Site')
    expect(submittedBody?.expected_status).toBe(404)
    expect(submittedBody?.timeout_seconds).toBe(25)
    expect(submittedBody?.failure_threshold).toBe(1)
    // Untouched, so it should carry the model's own default rather than
    // being omitted and left to the server to guess at.
    expect(submittedBody?.success_threshold).toBe(1)
  })

  it('offers a request body only for POST, and submits what was typed', async () => {
    let submittedBody: { method?: string; body?: string } | undefined
    let created = false
    server.use(
      http.get(`${BASE}/api/v1/monitors/`, () =>
        HttpResponse.json(paginated(created ? [makeMonitor({ name: 'New Site' })] : [])),
      ),
      http.post(`${BASE}/api/v1/monitors/`, async ({ request }) => {
        submittedBody = (await request.json()) as { method?: string; body?: string }
        created = true
        return HttpResponse.json(makeMonitor({ name: 'New Site' }), { status: 201 })
      }),
    )
    renderDashboard()
    await screen.findByText(/don't have any monitors yet/i)

    fireEvent.click(screen.getByRole('button', { name: 'New monitor' }))
    // GET is the default, and a body makes no sense there — the field
    // shouldn't exist at all until the method can actually carry one.
    expect(screen.queryByLabelText('Request body')).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Method'), { target: { value: 'POST' } })
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'New Site' } })
    fireEvent.change(screen.getByLabelText('URL'), {
      target: { value: 'https://newsite.example.com' },
    })
    fireEvent.change(screen.getByLabelText('Request body'), {
      target: { value: '{"probe": true}' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create monitor' }))

    await screen.findByText('New Site')
    expect(submittedBody?.method).toBe('POST')
    expect(submittedBody?.body).toBe('{"probe": true}')
  })

  it('sends an empty body when the method is switched away from POST', async () => {
    // The combination the API rejects outright: switching back to GET has
    // to clear the body on the way out, not send a stale one.
    let submittedBody: { method?: string; body?: string } | undefined
    let created = false
    server.use(
      http.get(`${BASE}/api/v1/monitors/`, () =>
        HttpResponse.json(paginated(created ? [makeMonitor({ name: 'New Site' })] : [])),
      ),
      http.post(`${BASE}/api/v1/monitors/`, async ({ request }) => {
        submittedBody = (await request.json()) as { method?: string; body?: string }
        created = true
        return HttpResponse.json(makeMonitor({ name: 'New Site' }), { status: 201 })
      }),
    )
    renderDashboard()
    await screen.findByText(/don't have any monitors yet/i)

    fireEvent.click(screen.getByRole('button', { name: 'New monitor' }))
    fireEvent.change(screen.getByLabelText('Method'), { target: { value: 'POST' } })
    fireEvent.change(screen.getByLabelText('Request body'), {
      target: { value: '{"probe": true}' },
    })
    fireEvent.change(screen.getByLabelText('Method'), { target: { value: 'GET' } })
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'New Site' } })
    fireEvent.change(screen.getByLabelText('URL'), {
      target: { value: 'https://newsite.example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create monitor' }))

    await screen.findByText('New Site')
    expect(submittedBody?.method).toBe('GET')
    expect(submittedBody?.body).toBe('')
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

  it('offers exactly the channels the API returns, and submits the selected one', async () => {
    // The backend already scopes /notification-channels/ to the current
    // user (IsOwner + channels_for_user) — this test isn't re-proving
    // that, it's proving the frontend doesn't do any of its own filtering
    // on top and just offers/sends whatever the API handed it.
    let submittedChannelIds: string[] | undefined
    let created = false
    server.use(
      http.get(`${BASE}/api/v1/monitors/`, () =>
        HttpResponse.json(paginated(created ? [makeMonitor({ name: 'New Site' })] : [])),
      ),
      http.get(`${BASE}/api/v1/notification-channels/`, () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 'cccccccc-0000-0000-0000-000000000001',
              type: 'EMAIL',
              name: 'Personal email',
              config: { email: 'dev@example.com' },
              is_verified: true,
              is_active: true,
              last_error: null,
              last_error_at: null,
              created_at: '2026-09-01T00:00:00Z',
              updated_at: '2026-09-01T00:00:00Z',
            },
          ],
        }),
      ),
      http.post(`${BASE}/api/v1/monitors/`, async ({ request }) => {
        const body = (await request.json()) as { notification_channel_ids?: string[] }
        submittedChannelIds = body.notification_channel_ids
        created = true
        return HttpResponse.json(makeMonitor({ name: 'New Site' }), { status: 201 })
      }),
    )
    renderDashboard()
    await screen.findByText(/don't have any monitors yet/i)

    fireEvent.click(screen.getByRole('button', { name: 'New monitor' }))
    expect(await screen.findByLabelText('Personal email (EMAIL)')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'New Site' } })
    fireEvent.change(screen.getByLabelText('URL'), {
      target: { value: 'https://newsite.example.com' },
    })
    fireEvent.click(screen.getByLabelText('Personal email (EMAIL)'))
    fireEvent.click(screen.getByRole('button', { name: 'Create monitor' }))

    await screen.findByText('New Site')
    expect(submittedChannelIds).toEqual(['cccccccc-0000-0000-0000-000000000001'])
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
