import { HttpResponse, http } from 'msw'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { server } from '../api/mocks/server'
import { renderWithProviders } from '../test/renderWithProviders'
import { useAuthStore } from '../auth/store'
import type { IncidentListItem } from '../api/types'
import { IncidentsPage } from './IncidentsPage'

const BASE = 'http://localhost:8000'
const INCIDENT_ID = 'aaaaaaaa-0000-0000-0000-000000000001'

function makeIncident(overrides: Partial<IncidentListItem> = {}): IncidentListItem {
  return {
    id: INCIDENT_ID,
    monitor: {
      id: 'bbbbbbbb-0000-0000-0000-000000000001',
      name: 'Prod API',
      url: 'https://example.com/',
      method: 'GET',
    },
    status: 'OPEN',
    started_at: '2026-09-01T10:00:00Z',
    acknowledged_at: null,
    resolved_at: null,
    duration_seconds: null,
    trigger_error_type: 'TIMEOUT',
    trigger_status_code: null,
    failed_checks_count: 3,
    ...overrides,
  }
}

function mockIncidents(results: IncidentListItem[], monitors: unknown[] = []) {
  server.use(
    http.get(`${BASE}/api/v1/incidents/`, () =>
      HttpResponse.json({ count: results.length, next: null, previous: null, results }),
    ),
    // The monitor filter dropdown fetches this unconditionally on mount.
    http.get(`${BASE}/api/v1/monitors/`, () =>
      HttpResponse.json({ count: monitors.length, next: null, previous: null, results: monitors }),
    ),
  )
}

// Only the handful of fields the filter's option list actually reads —
// the endpoint returns a lot more, none of which this page touches.
function makeFilterMonitor(overrides: Record<string, unknown> = {}) {
  return {
    id: 'cccccccc-0000-0000-0000-000000000001',
    name: 'test',
    url: 'https://a.example.com/',
    method: 'GET',
    ...overrides,
  }
}

beforeEach(() => {
  useAuthStore.getState().setAccessToken('test-token')
})

describe('IncidentsPage', () => {
  it('renders incidents with their status', async () => {
    mockIncidents([
      makeIncident({ status: 'OPEN' }),
      makeIncident({
        id: 'aaaaaaaa-0000-0000-0000-000000000002',
        status: 'RESOLVED',
        duration_seconds: 300,
      }),
    ])
    renderWithProviders(<IncidentsPage />)

    expect(await screen.findAllByText('Prod API')).toHaveLength(2)
    expect(screen.getByText('OPEN')).toBeInTheDocument()
    expect(screen.getByText('RESOLVED')).toBeInTheDocument()
  })

  it('acknowledges an open incident and hides the button once acknowledged', async () => {
    mockIncidents([makeIncident()])
    server.use(
      http.post(`${BASE}/api/v1/incidents/${INCIDENT_ID}/acknowledge/`, () =>
        HttpResponse.json(
          makeIncident({ status: 'ACKNOWLEDGED', acknowledged_at: '2026-09-01T10:05:00Z' }),
        ),
      ),
    )
    renderWithProviders(<IncidentsPage />)
    await screen.findByText('Prod API')

    fireEvent.click(screen.getByRole('button', { name: 'Acknowledge' }))

    await waitFor(() => expect(screen.getByText('ACKNOWLEDGED')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Acknowledge' })).not.toBeInTheDocument()
  })

  it('shows a distinct message when acknowledge 409s, not the generic error', async () => {
    mockIncidents([makeIncident()])
    server.use(
      http.post(`${BASE}/api/v1/incidents/${INCIDENT_ID}/acknowledge/`, () =>
        HttpResponse.json(
          { error: { code: 'conflict', message: 'Already handled.', details: null } },
          { status: 409 },
        ),
      ),
    )
    renderWithProviders(<IncidentsPage />)
    await screen.findByText('Prod API')

    fireEvent.click(screen.getByRole('button', { name: 'Acknowledge' }))

    expect(await screen.findByText(/already handled/i)).toBeInTheDocument()
    expect(screen.queryByText("Couldn't acknowledge. Try again.")).not.toBeInTheDocument()
  })

  it('shows a generic message on a non-409 acknowledge failure', async () => {
    mockIncidents([makeIncident()])
    server.use(
      http.post(`${BASE}/api/v1/incidents/${INCIDENT_ID}/acknowledge/`, () =>
        HttpResponse.json(
          { error: { code: 'error', message: 'Internal error.', details: null } },
          { status: 500 },
        ),
      ),
    )
    renderWithProviders(<IncidentsPage />)
    await screen.findByText('Prod API')

    fireEvent.click(screen.getByRole('button', { name: 'Acknowledge' }))

    expect(await screen.findByText("Couldn't acknowledge. Try again.")).toBeInTheDocument()
    expect(screen.queryByText(/already handled/i)).not.toBeInTheDocument()
  })

  it('shows the empty state when no incidents match the filters', async () => {
    mockIncidents([])
    renderWithProviders(<IncidentsPage />)

    expect(await screen.findByText(/no incidents match/i)).toBeInTheDocument()
  })

  it('shows the request method next to each incident', async () => {
    mockIncidents([
      makeIncident({ monitor: { ...makeIncident().monitor, method: 'POST' } as never }),
    ])
    renderWithProviders(<IncidentsPage />)

    expect(await screen.findByText('POST')).toBeInTheDocument()
  })

  it('keeps filter options readable when monitor names are unique', async () => {
    mockIncidents([], [makeFilterMonitor({ name: 'Prod API' })])
    renderWithProviders(<IncidentsPage />)

    // No method/URL suffix to wade through when the name already
    // identifies the monitor on its own.
    expect(await screen.findByRole('option', { name: 'Prod API' })).toBeInTheDocument()
  })

  it('disambiguates filter options when two monitors share a name', async () => {
    mockIncidents(
      [],
      [
        makeFilterMonitor({ method: 'GET', url: 'https://a.example.com/' }),
        makeFilterMonitor({
          id: 'cccccccc-0000-0000-0000-000000000002',
          method: 'POST',
          url: 'https://b.example.com/',
        }),
      ],
    )
    renderWithProviders(<IncidentsPage />)

    // Both are called "test"; without the suffix the dropdown offered two
    // identical entries and picking one was a guess.
    expect(
      await screen.findByRole('option', { name: 'test · GET · https://a.example.com/' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('option', { name: 'test · POST · https://b.example.com/' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'test' })).not.toBeInTheDocument()
  })
})
