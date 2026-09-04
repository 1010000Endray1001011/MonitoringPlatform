import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { HttpResponse, http } from 'msw'
import { describe, expect, it } from 'vitest'
import { server } from './mocks/server'
import { useCheckHistory } from './monitorDetail'
import type { CheckResult, CheckResultCursorPage } from './types'

const BASE = 'http://localhost:8000'
const MONITOR_ID = 'aaaaaaaa-0000-0000-0000-000000000001'

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
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

function page(results: CheckResult[]): CheckResultCursorPage {
  return { next: null, previous: null, results }
}

describe('useCheckHistory poll-until-newer', () => {
  it('keeps polling until a check newer than the baseline appears, then stops', async () => {
    let requestCount = 0
    // First couple of responses are still the stale check; from the third
    // request on, a genuinely newer one has "landed".
    server.use(
      http.get(`${BASE}/api/v1/monitors/${MONITOR_ID}/checks/`, () => {
        requestCount += 1
        const results =
          requestCount < 3
            ? [makeCheck({ id: 1, checked_at: '2026-09-03T10:00:00Z' })]
            : [makeCheck({ id: 2, checked_at: '2026-09-03T10:05:00Z' })]
        return HttpResponse.json(page(results))
      }),
    )

    const { result } = renderHook(
      () =>
        useCheckHistory(MONITOR_ID, {
          pollUntilNewerThan: '2026-09-03T10:00:00Z',
          pollIntervalMs: 20,
        }),
      { wrapper },
    )

    await waitFor(() => expect(result.current.data?.pages[0]?.results[0]?.id).toBe(2))
    const countRightAfterNewCheck = requestCount

    // Give it a moment to prove it actually stopped rather than just
    // happening to land on 2 mid-poll.
    await new Promise((resolve) => setTimeout(resolve, 100))
    expect(requestCount).toBe(countRightAfterNewCheck)
  })

  it('does not poll at all when no baseline is given', async () => {
    let requestCount = 0
    server.use(
      http.get(`${BASE}/api/v1/monitors/${MONITOR_ID}/checks/`, () => {
        requestCount += 1
        return HttpResponse.json(page([makeCheck()]))
      }),
    )

    renderHook(() => useCheckHistory(MONITOR_ID, { pollIntervalMs: 20 }), { wrapper })

    await waitFor(() => expect(requestCount).toBe(1))
    await new Promise((resolve) => setTimeout(resolve, 100))
    expect(requestCount).toBe(1)
  })
})

describe('useCheckHistory pagination', () => {
  it('fetches the next page using the absolute `next` URL the API returns', async () => {
    // The real backend answers with an absolute URL (scheme + host +
    // path + query) for `next`, per DRF's CursorPagination — this test
    // exists specifically to catch a regression where that URL gets
    // handed to apiClient.get() unconverted, which would double up the
    // origin and 404 rather than fetch page two.
    server.use(
      http.get(`${BASE}/api/v1/monitors/${MONITOR_ID}/checks/`, ({ request }) => {
        const cursor = new URL(request.url).searchParams.get('cursor')
        if (cursor === 'page2cursor') {
          return HttpResponse.json(
            page([makeCheck({ id: 2, checked_at: '2026-09-02T00:00:00Z' })]),
          )
        }
        return HttpResponse.json({
          next: `${BASE}/api/v1/monitors/${MONITOR_ID}/checks/?cursor=page2cursor&page_size=10`,
          previous: null,
          results: [makeCheck({ id: 1, checked_at: '2026-09-03T10:00:00Z' })],
        })
      }),
    )

    const { result } = renderHook(() => useCheckHistory(MONITOR_ID), { wrapper })

    await waitFor(() => expect(result.current.data?.pages).toHaveLength(1))
    expect(result.current.hasNextPage).toBe(true)

    result.current.fetchNextPage()

    await waitFor(() => expect(result.current.data?.pages).toHaveLength(2))
    expect(result.current.data?.pages[1]?.results[0]?.id).toBe(2)
    expect(result.current.hasNextPage).toBe(false)
  })
})
