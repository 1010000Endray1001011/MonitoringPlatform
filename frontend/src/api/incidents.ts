import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, apiClient } from './client'
import type { Incident, IncidentStatus, PaginatedIncidentList } from './types'

export interface IncidentListParams {
  status?: IncidentStatus
  monitor?: string
}

export function incidentsQueryKey(params: IncidentListParams = {}) {
  return ['incidents', params] as const
}

function buildIncidentsPath(params: IncidentListParams): string {
  const query = new URLSearchParams()
  if (params.status) query.set('status', params.status)
  if (params.monitor) query.set('monitor', params.monitor)
  const qs = query.toString()
  return `/api/v1/incidents/${qs ? `?${qs}` : ''}`
}

export function useIncidents(params: IncidentListParams = {}) {
  return useQuery({
    queryKey: incidentsQueryKey(params),
    queryFn: () => apiClient.get<PaginatedIncidentList>(buildIncidentsPath(params)),
  })
}

export function useAcknowledgeIncident() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiClient.post<Incident>(`/api/v1/incidents/${id}/acknowledge/`),
    // Patches every cached incidents list directly (regardless of which
    // status/monitor filter it was fetched with) rather than invalidating
    // and refetching — the mutation response already has the one thing
    // that changed (status, acknowledged_at), so there's nothing a refetch
    // would tell us that we don't already know.
    onSuccess: (data) => {
      queryClient.setQueriesData<PaginatedIncidentList>({ queryKey: ['incidents'] }, (old) => {
        if (!old) return old
        return {
          ...old,
          results: old.results.map((incident) =>
            incident.id === data.id
              ? { ...incident, status: data.status, acknowledged_at: data.acknowledged_at }
              : incident,
          ),
        }
      })
    },
    // A 409 means someone else (another tab, another session) already
    // acknowledged or resolved this incident between this screen's last
    // fetch and this click — the cached row's status is now provably
    // stale, not just unconfirmed, so it's worth a real refetch rather
    // than leaving the user staring at a now-wrong OPEN row.
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        queryClient.invalidateQueries({ queryKey: ['incidents'] })
      }
    },
  })
}
