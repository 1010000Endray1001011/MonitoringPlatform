import { Route, Routes } from 'react-router-dom'
import { HttpResponse, http } from 'msw'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { server } from '../api/mocks/server'
import { renderWithProviders } from '../test/renderWithProviders'
import { useAuthStore } from '../auth/store'
import type { CheckResult, MonitorDetail, MonitorStats } from '../api/types'
import { MonitorDetailPage } from './MonitorDetailPage'

const BASE = 'http://localhost:8000'
const MONITOR_ID = 'aaaaaaaa-0000-0000-0000-000000000001'

function makeMonitorDetail(overrides: Partial<MonitorDetail> = {}): MonitorDetail {
  return {
    id: MONITOR_ID,
    name: 'Prod API',
    url: 'https://example.com/health',
    method: 'GET',
    expected_status: 200,
    interval_seconds: 300,
    timeout_seconds: 10,
    headers: {},
    failure_threshold: 2,
    success_threshold: 1,
    is_enabled: true,
    status: 'UP',
    consecutive_failures: 0,
    consecutive_successes: 3,
    last_checked_at: '2026-09-03T10:00:00Z',
    last_response_time_ms: 120,
    open_incident_id: null,
    uptime_24h: 0.99,
    avg_response_time_24h_ms: 130,
    notification_channels: [],
    next_check_at: '2026-09-03T10:05:00Z',
    created_at: '2026-09-01T00:00:00Z',
    updated_at: '2026-09-01T00:00:00Z',
    ...overrides,
  }
}

function makeCheck(overrides: Partial<CheckResult> = {}): CheckResult {
  return {
    id: 1,
    checked_at: '2026-09-03T10:00:00Z',
    success: true,
    status_code: 200,
    response_time_ms: 100,
    error_type: null,
    error_message: null,
    response_size_bytes: 512,
    ...overrides,
  }
}

function makeStats(overrides: Partial<MonitorStats> = {}): MonitorStats {
  return {
    monitor_id: MONITOR_ID,
    period: '24h',
    period_from: '2026-09-02T10:00:00Z',
    period_to: '2026-09-03T10:00:00Z',
    summary: {
      uptime_ratio: 0.99,
      checks_total: 100,
      checks_failed: 1,
      avg_response_time_ms: 120,
      p95_response_time_ms: 200,
      incidents_count: 0,
      total_downtime_seconds: 0,
    },
    series: [],
    ...overrides,
  }
}

function mockDetailEndpoints(
  overrides: {
    monitor?: Partial<MonitorDetail>
    checks?: CheckResult[]
    stats?: Partial<MonitorStats>
  } = {},
) {
  server.use(
    http.get(`${BASE}/api/v1/monitors/${MONITOR_ID}/`, () =>
      HttpResponse.json(makeMonitorDetail(overrides.monitor)),
    ),
    http.get(`${BASE}/api/v1/monitors/${MONITOR_ID}/checks/`, () =>
      HttpResponse.json({ next: null, previous: null, results: overrides.checks ?? [] }),
    ),
    http.get(`${BASE}/api/v1/monitors/${MONITOR_ID}/stats/`, () =>
      HttpResponse.json(makeStats(overrides.stats)),
    ),
  )
}

function renderDetailPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/monitors/:id" element={<MonitorDetailPage />} />
      <Route path="/dashboard" element={<div>Dashboard placeholder</div>} />
    </Routes>,
    { route: `/monitors/${MONITOR_ID}` },
  )
}

beforeEach(() => {
  useAuthStore.getState().setAccessToken('test-token')
  // MonitorEditForm's channel multiselect fetches this unconditionally
  // once the edit form mounts — an empty default here keeps every test
  // that doesn't care about channels from having to know that.
  server.use(
    http.get(`${BASE}/api/v1/notification-channels/`, () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
  )
})

describe('MonitorDetailPage', () => {
  it('renders monitor summary, stats, and check history', async () => {
    mockDetailEndpoints({ checks: [makeCheck()] })
    renderDetailPage()

    expect(await screen.findByText('Prod API')).toBeInTheDocument()
    expect(screen.getByText('UP')).toBeInTheDocument()
    expect(screen.getByText('https://example.com/health')).toBeInTheDocument()
    expect(await screen.findByText('200')).toBeInTheDocument() // status_code column

    // Period summary — must reflect the selected-period stats.summary,
    // not just feed the chart, per docs/ROADMAP.md's "summary + series".
    expect(
      await screen.findByText(
        'Uptime: 99.0% · Checks: 100 (1 failed) · Incidents: 0 · Downtime: 0m',
      ),
    ).toBeInTheDocument()
  })

  it('loads more check history when "Load more" is clicked', async () => {
    mockDetailEndpoints()
    server.use(
      http.get(`${BASE}/api/v1/monitors/${MONITOR_ID}/checks/`, ({ request }) => {
        const cursor = new URL(request.url).searchParams.get('cursor')
        if (cursor === 'older') {
          return HttpResponse.json({
            next: null,
            previous: null,
            results: [makeCheck({ id: 2, checked_at: '2026-09-02T00:00:00Z' })],
          })
        }
        return HttpResponse.json({
          next: `${BASE}/api/v1/monitors/${MONITOR_ID}/checks/?cursor=older&page_size=10`,
          previous: null,
          results: [makeCheck({ id: 1, checked_at: '2026-09-03T10:00:00Z' })],
        })
      }),
    )
    renderDetailPage()
    await screen.findByText('Prod API')

    // Both checks default to status_code 200, so counting "200" cells is
    // a simple stand-in for "how many check rows are on screen" that
    // doesn't depend on react95's Table markup exposing table-row roles.
    expect(await screen.findAllByText('200')).toHaveLength(1)

    fireEvent.click(screen.getByRole('button', { name: 'Load more' }))

    await waitFor(() => expect(screen.getAllByText('200')).toHaveLength(2))
    // Both pages' rows stay visible at once — "load more" appends, it
    // doesn't replace what was already on screen.
    expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument()
  })

  it('shows empty-state messages for a monitor with no history or stats data yet', async () => {
    mockDetailEndpoints({ checks: [], stats: { series: [] } })
    renderDetailPage()

    await screen.findByText('Prod API')
    expect(await screen.findByText(/no checks recorded yet/i)).toBeInTheDocument()
    expect(await screen.findByText(/no data for this period/i)).toBeInTheDocument()
  })

  it('shows an open-incident indicator when the monitor has one', async () => {
    mockDetailEndpoints({ monitor: { open_incident_id: 'bbbbbbbb-0000-0000-0000-000000000002' } })
    renderDetailPage()

    expect(await screen.findByText(/open incident/i)).toBeInTheDocument()
  })

  it('triggers a manual check and disables the button while waiting for a result', async () => {
    mockDetailEndpoints({ checks: [makeCheck()] })
    server.use(
      http.post(`${BASE}/api/v1/monitors/${MONITOR_ID}/check/`, () =>
        HttpResponse.json({ detail: 'Check has been queued.', poll_url: '' }, { status: 202 }),
      ),
    )
    renderDetailPage()
    await screen.findByText('Prod API')

    fireEvent.click(screen.getByRole('button', { name: 'Check now' }))

    expect(await screen.findByRole('button', { name: /waiting for result/i })).toBeDisabled()
  })

  it('saves an edit and shows the updated name', async () => {
    mockDetailEndpoints()
    server.use(
      http.patch(`${BASE}/api/v1/monitors/${MONITOR_ID}/`, async ({ request }) => {
        const body = (await request.json()) as { name?: string }
        return HttpResponse.json(makeMonitorDetail({ name: body.name ?? 'Prod API' }))
      }),
    )
    renderDetailPage()
    await screen.findByText('Prod API')

    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Renamed API' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByText('Renamed API')).toBeInTheDocument()
  })

  it('shows the validation error when timeout_seconds >= interval_seconds', async () => {
    mockDetailEndpoints()
    server.use(
      http.patch(`${BASE}/api/v1/monitors/${MONITOR_ID}/`, () =>
        HttpResponse.json(
          {
            error: {
              code: 'validation_error',
              message: 'Validation failed.',
              details: {
                timeout_seconds: ['timeout_seconds must be less than interval_seconds.'],
              },
            },
          },
          { status: 400 },
        ),
      ),
    )
    renderDetailPage()
    await screen.findByText('Prod API')

    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(
      await screen.findByText('timeout_seconds must be less than interval_seconds.'),
    ).toBeInTheDocument()
    // Still on the edit form, not silently dropped back to the summary view.
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeInTheDocument()
  })

  it('deletes the monitor after confirmation and returns to the dashboard', async () => {
    mockDetailEndpoints()
    let deleteCalled = false
    server.use(
      http.delete(`${BASE}/api/v1/monitors/${MONITOR_ID}/`, () => {
        deleteCalled = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderDetailPage()
    await screen.findByText('Prod API')

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm delete' }))

    await waitFor(() => expect(screen.getByText('Dashboard placeholder')).toBeInTheDocument())
    expect(deleteCalled).toBe(true)
  })
})
