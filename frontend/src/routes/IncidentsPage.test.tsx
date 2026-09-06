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

function mockIncidents(results: IncidentListItem[]) {
  server.use(
    http.get(`${BASE}/api/v1/incidents/`, () =>
      HttpResponse.json({ count: results.length, next: null, previous: null, results }),
    ),
    // The monitor filter dropdown fetches this unconditionally on mount.
    http.get(`${BASE}/api/v1/monitors/`, () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
  )
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
})
