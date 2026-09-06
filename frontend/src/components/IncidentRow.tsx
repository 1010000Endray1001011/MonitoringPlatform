import { useNavigate } from 'react-router-dom'
import { Button, TableDataCell, TableRow } from 'react95'
import { ApiError } from '../api/client'
import { useAcknowledgeIncident } from '../api/incidents'
import type { IncidentListItem } from '../api/types'
import { IncidentStatusBadge } from './IncidentStatusBadge'

function formatDuration(totalSeconds: number | null): string {
  if (totalSeconds === null) return 'ongoing'
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.round((totalSeconds % 3600) / 60)
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`
}

interface IncidentRowProps {
  incident: IncidentListItem
}

export function IncidentRow({ incident }: IncidentRowProps) {
  const navigate = useNavigate()
  const acknowledge = useAcknowledgeIncident()

  // A 409 means this exact row is stale (acknowledged/resolved elsewhere
  // between fetch and click) — worth a distinct message rather than the
  // same generic "couldn't acknowledge, try again" a network error would
  // get, since retrying identically would just 409 again.
  const isStale =
    acknowledge.isError &&
    acknowledge.error instanceof ApiError &&
    acknowledge.error.status === 409

  return (
    <TableRow>
      <TableDataCell>
        <Button onClick={() => navigate(`/monitors/${incident.monitor.id}`)}>
          {incident.monitor.name}
        </Button>
      </TableDataCell>
      <TableDataCell>
        <IncidentStatusBadge status={incident.status} />
      </TableDataCell>
      <TableDataCell>{new Date(incident.started_at).toLocaleString()}</TableDataCell>
      <TableDataCell>{formatDuration(incident.duration_seconds)}</TableDataCell>
      <TableDataCell>{incident.trigger_error_type ?? '—'}</TableDataCell>
      <TableDataCell>
        {incident.status === 'OPEN' && (
          <>
            <Button
              onClick={() => acknowledge.mutate(incident.id)}
              disabled={acknowledge.isPending}
            >
              {acknowledge.isPending ? 'Acknowledging…' : 'Acknowledge'}
            </Button>
            {isStale && <p role="alert">This incident was already handled — refreshing…</p>}
            {acknowledge.isError && !isStale && (
              <p role="alert">Couldn't acknowledge. Try again.</p>
            )}
          </>
        )}
      </TableDataCell>
    </TableRow>
  )
}
