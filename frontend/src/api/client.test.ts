import { HttpResponse, http } from 'msw'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { server } from './mocks/server'
import { apiClient, ApiError } from './client'
import { useAuthStore } from '../auth/store'

const BASE = 'http://localhost:8000'

describe('apiClient', () => {
  beforeEach(() => {
    useAuthStore.getState().clearAccessToken()
  })

  it('sends the access token as a Bearer header when one is set', async () => {
    useAuthStore.getState().setAccessToken('my-token')
    let seenAuthHeader: string | null = null
    server.use(
      http.get(`${BASE}/api/v1/whoami`, ({ request }) => {
        seenAuthHeader = request.headers.get('authorization')
        return HttpResponse.json({ ok: true })
      }),
    )

    await apiClient.get('/api/v1/whoami')

    expect(seenAuthHeader).toBe('Bearer my-token')
  })

  it('on a 401, refreshes the token and retries the original request once', async () => {
    useAuthStore.getState().setAccessToken('stale-token')
    let whoamiCallCount = 0
    server.use(
      http.get(`${BASE}/api/v1/whoami`, ({ request }) => {
        whoamiCallCount += 1
        const auth = request.headers.get('authorization')
        if (auth === 'Bearer stale-token') {
          return HttpResponse.json({ error: 'expired' }, { status: 401 })
        }
        return HttpResponse.json({ ok: true, auth })
      }),
      http.post(`${BASE}/api/v1/auth/token/refresh`, () =>
        HttpResponse.json({ access: 'fresh-token' }),
      ),
    )

    const result = await apiClient.get<{ ok: boolean; auth: string }>('/api/v1/whoami')

    expect(whoamiCallCount).toBe(2)
    expect(result.auth).toBe('Bearer fresh-token')
    expect(useAuthStore.getState().accessToken).toBe('fresh-token')
  })

  it('redirects to /login when refresh also fails', async () => {
    // jsdom's window.location.assign isn't a plain configurable property,
    // so it can't be spied on directly — stubbing the whole location object
    // is the standard workaround.
    const assign = vi.fn()
    const originalLocation = window.location
    Object.defineProperty(window, 'location', {
      value: { ...originalLocation, assign },
      writable: true,
    })

    useAuthStore.getState().setAccessToken('stale-token')
    server.use(
      http.get(`${BASE}/api/v1/whoami`, () => HttpResponse.json({}, { status: 401 })),
      http.post(`${BASE}/api/v1/auth/token/refresh`, () => HttpResponse.json({}, { status: 401 })),
    )

    await expect(apiClient.get('/api/v1/whoami')).rejects.toThrow(ApiError)

    expect(assign).toHaveBeenCalledWith('/login')
    expect(useAuthStore.getState().accessToken).toBeNull()
    Object.defineProperty(window, 'location', { value: originalLocation, writable: true })
  })

  it('does not attempt a refresh when the login endpoint itself returns 401', async () => {
    let refreshCallCount = 0
    server.use(
      http.post(`${BASE}/api/v1/auth/token`, () => HttpResponse.json({}, { status: 401 })),
      http.post(`${BASE}/api/v1/auth/token/refresh`, () => {
        refreshCallCount += 1
        return HttpResponse.json({ access: 'irrelevant' })
      }),
    )

    await expect(
      apiClient.post('/api/v1/auth/token', { email: 'a@b.com', password: 'wrong' }),
    ).rejects.toMatchObject({ status: 401 })

    expect(refreshCallCount).toBe(0)
  })

  it('raises ApiError with the response status and body on a non-401 failure', async () => {
    server.use(
      http.post(`${BASE}/api/v1/monitors/`, () =>
        HttpResponse.json({ error: { code: 'validation_error' } }, { status: 400 }),
      ),
    )

    const error = await apiClient.post('/api/v1/monitors/', {}).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(400)
    expect((error as ApiError).body).toEqual({ error: { code: 'validation_error' } })
  })
})
