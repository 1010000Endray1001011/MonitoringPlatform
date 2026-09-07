import { useState } from 'react'
import { SelectNative, Table, TableBody, TableHead, TableHeadCell, TableRow } from 'react95'
import { useIncidents } from '../api/incidents'
import { useMonitors } from '../api/monitors'
import type { IncidentStatus } from '../api/types'
import { IncidentRow } from '../components/IncidentRow'
import { NavBar } from '../components/NavBar'
import { PageLayout } from '../components/PageLayout'

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

  // Monitor names aren't unique, so a plain name-only list could show the
  // same word several times with no way to tell which entry is which —
  // picking one of them was effectively a coin flip. The method and URL
  // are appended only to names that actually repeat, so the common case
  // (every monitor named differently) stays short and readable and only
  // genuinely ambiguous entries pay for the extra text.
  const monitorsList = monitors.data?.results ?? []
  const nameCounts = new Map<string, number>()
  for (const monitor of monitorsList) {
    nameCounts.set(monitor.name, (nameCounts.get(monitor.name) ?? 0) + 1)
  }

  const monitorOptions = [
    { label: 'All monitors', value: '' },
    ...monitorsList.map((monitor) => ({
      label:
        (nameCounts.get(monitor.name) ?? 0) > 1
          ? `${monitor.name} · ${monitor.method} · ${monitor.url}`
          : monitor.name,
      value: monitor.id,
    })),
  ]

  return (
    <PageLayout title="Incidents">
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
              <TableHeadCell>Method</TableHeadCell>
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
    </PageLayout>
  )
}
