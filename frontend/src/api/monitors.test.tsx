import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from './mocks/server'
import { useMonitors } from './monitors'

const BASE = 'http://localhost:8000'

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

describe('useMonitors polling', () => {
  it('refetches on the given interval', async () => {
    // A real, short interval instead of faking global timers — combining
    // fake timers with MSW's fetch-based mocking is a well-known source of
    // deadlocked tests; a real 30ms wait is both fast and actually exercises
    // the real refetchInterval mechanism rather than a stand-in for it.
    let requestCount = 0
    server.use(
      http.get(`${BASE}/api/v1/monitors/`, () => {
        requestCount += 1
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] })
      }),
    )

    renderHook(() => useMonitors({}, 30), { wrapper })

    await waitFor(() => expect(requestCount).toBeGreaterThanOrEqual(2))
  })
})
