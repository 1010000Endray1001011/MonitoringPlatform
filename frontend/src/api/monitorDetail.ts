import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import { MONITORS_REFETCH_INTERVAL_MS, monitorDetailQueryKey, monitorsQueryKey } from './monitors'
import type {
  CheckResultCursorPage,
  ImmediateCheckAccepted,
  MonitorDetail,
  MonitorPatchRequest,
  MonitorStats,
  StatsPeriod,
} from './types'

export function useMonitorDetail(
  monitorId: string,
  refetchInterval: number = MONITORS_REFETCH_INTERVAL_MS,
) {
  return useQuery({
    queryKey: monitorDetailQueryKey(monitorId),
    queryFn: () => apiClient.get<MonitorDetail>(`/api/v1/monitors/${monitorId}/`),
    refetchInterval,
  })
}

export function useMonitorStats(monitorId: string, period: StatsPeriod) {
  return useQuery({
    queryKey: ['monitor', monitorId, 'stats', period],
    queryFn: () =>
      apiClient.get<MonitorStats>(`/api/v1/monitors/${monitorId}/stats/?period=${period}`),
  })
}

interface UseCheckHistoryOptions {
  // Set right before triggering a manual check to the most recent check's
  // timestamp at that moment — the query then polls every few seconds
  // until a check newer than this shows up, and stops on its own the
  // instant it does. Omit (or clear back to undefined once satisfied) for
  // the normal, one-shot fetch with no aggressive polling.
  pollUntilNewerThan?: string
  pollIntervalMs?: number
}

const CHECK_NOW_POLL_INTERVAL_MS = 2_000
const CHECK_HISTORY_PAGE_SIZE = 10

// The cursor endpoint's `next`/`previous` are always absolute URLs (DRF's
// CursorPagination builds them from request.build_absolute_uri()), but
// apiClient.get() unconditionally prepends its own API_BASE_URL onto
// whatever path it's given — passing the absolute URL straight through
// would double up the origin. Cutting it back down to path+query is what
// makes it safe to hand to apiClient.get() as the next page's request.
function toRequestPath(absoluteUrl: string): string {
  const url = new URL(absoluteUrl)
  return `${url.pathname}${url.search}`
}

// Infinite rather than a single fixed page: FRONTEND.md's spec for this
// screen calls for a "load more" cursor feed, not a top-N snapshot, so
// older history stays reachable instead of vanishing past the first page.
export function useCheckHistory(monitorId: string, options: UseCheckHistoryOptions = {}) {
  const pollIntervalMs = options.pollIntervalMs ?? CHECK_NOW_POLL_INTERVAL_MS
  return useInfiniteQuery({
    queryKey: ['monitor', monitorId, 'checks'],
    queryFn: ({ pageParam }: { pageParam: string | null }) =>
      apiClient.get<CheckResultCursorPage>(
        pageParam ?? `/api/v1/monitors/${monitorId}/checks/?page_size=${CHECK_HISTORY_PAGE_SIZE}`,
      ),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => (lastPage.next ? toRequestPath(lastPage.next) : undefined),
    refetchInterval: (query) => {
      if (!options.pollUntilNewerThan) return false
      // Only page 0 (the most recent checks) can ever contain a result
      // newer than the poll baseline — later pages are strictly older.
      const latest = query.state.data?.pages[0]?.results[0]
      if (latest && latest.checked_at > options.pollUntilNewerThan) return false
      return pollIntervalMs
    },
  })
}

export function useTriggerCheck(monitorId: string) {
  return useMutation({
    mutationFn: () =>
      apiClient.post<ImmediateCheckAccepted>(`/api/v1/monitors/${monitorId}/check/`),
  })
}

export function useUpdateMonitor(monitorId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: MonitorPatchRequest) =>
      apiClient.patch<MonitorDetail>(`/api/v1/monitors/${monitorId}/`, body),
    onSuccess: (data) => {
      queryClient.setQueryData(monitorDetailQueryKey(monitorId), data)
      queryClient.invalidateQueries({ queryKey: monitorsQueryKey() })
    },
  })
}

export function useDeleteMonitor() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (monitorId: string) => apiClient.delete<void>(`/api/v1/monitors/${monitorId}/`),
    onSuccess: (_data, monitorId) => {
      queryClient.removeQueries({ queryKey: monitorDetailQueryKey(monitorId) })
      queryClient.invalidateQueries({ queryKey: ['monitors'] })
    },
  })
}
