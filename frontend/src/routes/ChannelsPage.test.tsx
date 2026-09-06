import { HttpResponse, http } from 'msw'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { server } from '../api/mocks/server'
import { renderWithProviders } from '../test/renderWithProviders'
import { useAuthStore } from '../auth/store'
import type { NotificationChannel } from '../api/types'
import { ChannelsPage } from './ChannelsPage'

const BASE = 'http://localhost:8000'
const CHANNEL_ID = 'cccccccc-0000-0000-0000-000000000001'

function makeChannel(overrides: Partial<NotificationChannel> = {}): NotificationChannel {
  return {
    id: CHANNEL_ID,
    type: 'EMAIL',
    name: 'Personal email',
    config: { email: 'dev@example.com' },
    is_verified: false,
    is_active: true,
    last_error: null,
    last_error_at: null,
    created_at: '2026-09-01T00:00:00Z',
    updated_at: '2026-09-01T00:00:00Z',
    ...overrides,
  }
}

function mockChannels(results: NotificationChannel[]) {
  server.use(
    http.get(`${BASE}/api/v1/notification-channels/`, () =>
      HttpResponse.json({ count: results.length, next: null, previous: null, results }),
    ),
  )
}

beforeEach(() => {
  useAuthStore.getState().setAccessToken('test-token')
})

describe('ChannelsPage', () => {
  it('renders channels with their verification status', async () => {
    mockChannels([
      makeChannel({ is_verified: true }),
      makeChannel({
        id: 'cccccccc-0000-0000-0000-000000000002',
        name: 'Ops chat',
        type: 'TELEGRAM',
      }),
    ])
    renderWithProviders(<ChannelsPage />)

    expect(await screen.findByText('Personal email')).toBeInTheDocument()
    expect(screen.getByText('Verified')).toBeInTheDocument()
    expect(screen.getByText('Ops chat')).toBeInTheDocument()
    expect(screen.getByText('Not verified')).toBeInTheDocument()
  })

  it('shows the empty state with no channels', async () => {
    mockChannels([])
    renderWithProviders(<ChannelsPage />)

    expect(await screen.findByText(/don't have any notification channels/i)).toBeInTheDocument()
  })

  it('creates an email channel and shows it in the list', async () => {
    let created = false
    server.use(
      http.get(`${BASE}/api/v1/notification-channels/`, () =>
        HttpResponse.json({
          count: created ? 1 : 0,
          next: null,
          previous: null,
          results: created ? [makeChannel()] : [],
        }),
      ),
      http.post(`${BASE}/api/v1/notification-channels/`, async ({ request }) => {
        const body = (await request.json()) as {
          name: string
          type: 'EMAIL' | 'TELEGRAM'
          config: unknown
        }
        created = true
        return HttpResponse.json(makeChannel({ name: body.name, config: body.config }), {
          status: 201,
        })
      }),
    )
    renderWithProviders(<ChannelsPage />)
    await screen.findByText(/don't have any notification channels/i)

    fireEvent.click(screen.getByRole('button', { name: 'New channel' }))
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Personal email' } })
    fireEvent.change(screen.getByLabelText('Email address'), {
      target: { value: 'dev@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create channel' }))

    expect(await screen.findByText('Personal email')).toBeInTheDocument()
  })

  it('verify shows loading then a success state', async () => {
    mockChannels([makeChannel()])
    // MSW resolves a plain handler fast enough that the "Verifying…" state
    // is usually gone before any assertion — real or fake timers — gets a
    // chance to observe it (same class of race as fake-timers-plus-MSW
    // elsewhere in this app). Holding the response open on a promise the
    // test controls is what makes the intermediate state observable on
    // purpose instead of by timing luck.
    let resolveVerify: () => void = () => {}
    server.use(
      http.post(`${BASE}/api/v1/notification-channels/${CHANNEL_ID}/verify/`, async () => {
        await new Promise<void>((resolve) => {
          resolveVerify = resolve
        })
        return HttpResponse.json(makeChannel({ is_verified: true }))
      }),
    )
    renderWithProviders(<ChannelsPage />)
    await screen.findByText('Personal email')

    fireEvent.click(screen.getByRole('button', { name: 'Verify' }))

    expect(await screen.findByRole('button', { name: 'Verifying…' })).toBeDisabled()

    resolveVerify()

    expect(await screen.findByRole('button', { name: 'Verified ✓' })).toBeInTheDocument()
    expect(screen.getByText('Verified')).toBeInTheDocument()
  })

  it('verify shows the specific failure message, not a generic one', async () => {
    mockChannels([makeChannel()])
    server.use(
      http.post(`${BASE}/api/v1/notification-channels/${CHANNEL_ID}/verify/`, () =>
        HttpResponse.json(
          {
            error: {
              code: 'validation_error',
              message: 'Could not deliver a test message to this channel.',
              details: { config: ['Telegram: chat not found (400).'] },
            },
          },
          { status: 400 },
        ),
      ),
    )
    renderWithProviders(<ChannelsPage />)
    await screen.findByText('Personal email')

    fireEvent.click(screen.getByRole('button', { name: 'Verify' }))

    expect(await screen.findByText('Telegram: chat not found (400).')).toBeInTheDocument()
    // Back to idle, not stuck showing "Verifying…" or a disabled button.
    expect(screen.getByRole('button', { name: 'Verify' })).toBeEnabled()
  })

  it('deletes a channel after confirmation', async () => {
    let deleted = false
    server.use(
      http.get(`${BASE}/api/v1/notification-channels/`, () =>
        HttpResponse.json({
          count: deleted ? 0 : 1,
          next: null,
          previous: null,
          results: deleted ? [] : [makeChannel()],
        }),
      ),
      http.delete(`${BASE}/api/v1/notification-channels/${CHANNEL_ID}/`, () => {
        deleted = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    renderWithProviders(<ChannelsPage />)
    await screen.findByText('Personal email')

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm delete' }))

    await waitFor(() => expect(screen.queryByText('Personal email')).not.toBeInTheDocument())
  })
})
