import { useState } from 'react'
import {
  SelectNative,
  Table,
  TableBody,
  TableHead,
  TableHeadCell,
  TableRow,
  Window,
  WindowContent,
  WindowHeader,
} from 'react95'
import { useIncidents } from '../api/incidents'
import { useMonitors } from '../api/monitors'
import type { IncidentStatus } from '../api/types'
import { IncidentRow } from '../components/IncidentRow'
import { NavBar } from '../components/NavBar'

const STATUS_OPTIONS: { label: string; value: IncidentStatus | '' }[] = [
  { label: 'All statuses', value: '' },
  { label: 'Open', value: 'OPEN' },
  { label: 'Acknowledged', value: 'ACKNOWLEDGED' },
  { label: 'Resolved', value: 'RESOLVED' },
]

export function IncidentsPage() {
  const [status, setStatus] = useState<IncidentStatus | ''>('')
  const [monitorId, setMonitorId] = useState('')

  // Reuses the same monitors list already built for the dashboard purely
  // to populate the filter's options — no new endpoint, no new hook.
  const monitors = useMonitors()
  const incidents = useIncidents({
    status: status || undefined,
    monitor: monitorId || undefined,
  })

  const monitorOptions = [
    { label: 'All monitors', value: '' },
    ...(monitors.data?.results.map((monitor) => ({ label: monitor.name, value: monitor.id })) ??
      []),
  ]

  return (
    <Window>
      <WindowHeader>Incidents</WindowHeader>
      <WindowContent>
        <NavBar />

        <label>
          Status
          <SelectNative
            options={STATUS_OPTIONS}
            value={status}
            onChange={(option) => setStatus(option.value as IncidentStatus | '')}
          />
        </label>

        <label>
          Monitor
          <SelectNative
            options={monitorOptions}
            value={monitorId}
            onChange={(option) => setMonitorId(option.value as string)}
          />
        </label>

        {incidents.isLoading && <p>Loading…</p>}
        {incidents.isError && <p role="alert">Couldn't load incidents. Try reloading.</p>}

        {incidents.data && incidents.data.results.length === 0 && (
          <p>No incidents match these filters.</p>
        )}

        {incidents.data && incidents.data.results.length > 0 && (
          <Table>
            <TableHead>
              <TableRow>
                <TableHeadCell>Monitor</TableHeadCell>
                <TableHeadCell>Status</TableHeadCell>
                <TableHeadCell>Started</TableHeadCell>
                <TableHeadCell>Duration</TableHeadCell>
                <TableHeadCell>Trigger</TableHeadCell>
                <TableHeadCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {incidents.data.results.map((incident) => (
                <IncidentRow key={incident.id} incident={incident} />
              ))}
            </TableBody>
          </Table>
        )}
      </WindowContent>
    </Window>
  )
}
