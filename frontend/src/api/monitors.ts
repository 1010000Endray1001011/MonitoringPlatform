import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'
import type {
  MonitorDetail,
  MonitorStatus,
  MonitorWriteRequest,
  PaginatedMonitorList,
} from './types'

export interface MonitorListParams {
  search?: string
  status?: string
}

// A stable, shared key prefix so pause/resume/create mutations can
// invalidate (or optimistically patch) every active list query — including
// ones with a different search/status filter than whichever screen
// triggered the mutation — without each caller having to know about the
// others' filters.
export function monitorsQueryKey(params: MonitorListParams = {}) {
  return ['monitors', params] as const
}

// Singular key for one monitor's own detail query (monitorDetail.ts) — kept
// here, next to the list key, so mutations in this file can invalidate both
// without monitorDetail.ts needing to be imported back into this one.
export function monitorDetailQueryKey(id: string) {
  return ['monitor', id] as const
}

function buildMonitorsPath(params: MonitorListParams): string {
  const query = new URLSearchParams()
  if (params.search) query.set('search', params.search)
  if (params.status) query.set('status', params.status)
  const qs = query.toString()
  return `/api/v1/monitors/${qs ? `?${qs}` : ''}`
}

// A monitor can flip UP/DOWN or gain an incident at any moment, independent
// of anything the user does on this screen — polling is the only way this
// list would ever reflect that. 20s sits in the middle of the 15-30s range:
// frequent enough to feel live next to a 30s dispatcher tick, not so
// frequent it's polling faster than the data underneath it could possibly
// change.
export const MONITORS_REFETCH_INTERVAL_MS = 20_000

export function useMonitors(
  params: MonitorListParams = {},
  refetchInterval: number = MONITORS_REFETCH_INTERVAL_MS,
) {
  return useQuery({
    queryKey: monitorsQueryKey(params),
    queryFn: () => apiClient.get<PaginatedMonitorList>(buildMonitorsPath(params)),
    refetchInterval,
  })
}

export function useCreateMonitor() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: MonitorWriteRequest) =>
      apiClient.post<MonitorDetail>('/api/v1/monitors/', body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['monitors'] })
    },
  })
}

function setMonitorInAllLists(
  queryClient: ReturnType<typeof useQueryClient>,
  id: string,
  patch: Partial<Pick<MonitorStatus, 'status' | 'is_enabled'>>,
) {
  queryClient.setQueriesData<PaginatedMonitorList>({ queryKey: ['monitors'] }, (old) => {
    if (!old) return old
    return {
      ...old,
      results: old.results.map((monitor) =>
        monitor.id === id ? { ...monitor, ...patch } : monitor,
      ),
    }
  })
}

function useSetEnabledMutation(action: 'pause' | 'resume', nextEnabled: boolean) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiClient.post<MonitorStatus>(`/api/v1/monitors/${id}/${action}/`),
    // Optimistic, but only for what the client can actually predict
    // correctly: pausing always shows "PAUSED" regardless of health
    // (that's how the backend computes it too), so that guess is safe.
    // Resuming brings back whatever health_status the monitor had before
    // it was paused — UP, DOWN, or NEW — and the client has no way to know
    // which, so `status` is deliberately left alone here rather than
    // guessed; it catches up for real once onSettled's invalidation lands.
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['monitors'] })
      const previous = queryClient.getQueriesData<PaginatedMonitorList>({
        queryKey: ['monitors'],
      })
      setMonitorInAllLists(queryClient, id, {
        is_enabled: nextEnabled,
        ...(action === 'pause' ? { status: 'PAUSED' } : {}),
      })
      return { previous }
    },
    onError: (_error, _id, context) => {
      context?.previous.forEach(([queryKey, data]) => queryClient.setQueryData(queryKey, data))
    },
    onSettled: (_data, _error, id) => {
      queryClient.invalidateQueries({ queryKey: ['monitors'] })
      queryClient.invalidateQueries({ queryKey: monitorDetailQueryKey(id) })
    },
  })
}

export function usePauseMonitor() {
  return useSetEnabledMutation('pause', false)
}

export function useResumeMonitor() {
  return useSetEnabledMutation('resume', true)
}
