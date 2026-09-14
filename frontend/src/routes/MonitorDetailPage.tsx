import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, SelectNative } from 'react95'
import {
  useCheckHistory,
  useDeleteMonitor,
  useMonitorDetail,
  useMonitorStats,
  useTriggerCheck,
} from '../api/monitorDetail'
import { ApiError } from '../api/client'
import type { MonitorStats, StatsPeriod } from '../api/types'
import { CheckHistoryList } from '../components/CheckHistoryList'
import { MonitorEditForm } from '../components/MonitorEditForm'
import { NavBar } from '../components/NavBar'
import { PageLayout } from '../components/PageLayout'
import { OpenIncidentFlag } from '../components/OpenIncidentFlag'
import { StatusBadge } from '../components/StatusBadge'
import { StatsChart } from '../components/StatsChart'

const PERIOD_OPTIONS: { label: string; value: StatsPeriod }[] = [
  { label: 'Last 24 hours', value: '24h' },
  { label: 'Last 7 days', value: '7d' },
  { label: 'Last 30 days', value: '30d' },
]

// The epoch stand-in for "no check has ever happened yet" — any real
// checked_at timestamp sorts after this, so the polling condition in
// useCheckHistory (`latest.checked_at > pollBaseline`) is satisfied by
// the very first check a brand-new monitor ever records.
const BEFORE_ANY_CHECK = '1970-01-01T00:00:00Z'

function describeCheckError(error: unknown): string {
  if (error instanceof ApiError) {
    // 5/min per user, deliberately tighter than the general rate: this
    // endpoint makes our own infrastructure call an arbitrary URL.
    if (error.status === 429) {
      return 'Too many manual checks — this is limited to 5 per minute. Wait a moment, then try again.'
    }
    if (error.status === 409) {
      return "This monitor is paused, so it won't run checks. Resume it from the dashboard first."
    }
  }
  return "Couldn't queue the check. Try again."
}

// total_downtime_seconds comes back as a raw integer — this is purely a
// display nicety, not needed anywhere else, so it stays local instead of
// becoming a shared util for one call site.
function formatDowntime(totalSeconds: number): string {
  if (totalSeconds === 0) return '0m'
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.round((totalSeconds % 3600) / 60)
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`
}

// Built as a single string rather than inline JSX expressions — JSX
// collapses/introduces whitespace around multi-line text+expression mixes
// in ways that are easy to get subtly wrong, and this way the exact
// rendered text is trivial to assert on in tests.
function formatPeriodSummary(summary: MonitorStats['summary']): string {
  const uptimeText =
    summary.uptime_ratio === null ? '—' : `${(summary.uptime_ratio * 100).toFixed(1)}%`
  return (
    `Uptime: ${uptimeText} · Checks: ${summary.checks_total} (${summary.checks_failed} failed) ` +
    `· Incidents: ${summary.incidents_count} · Downtime: ${formatDowntime(summary.total_downtime_seconds)}`
  )
}

export function MonitorDetailPage() {
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [period, setPeriod] = useState<StatsPeriod>('24h')
  const [isEditing, setIsEditing] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [pollBaseline, setPollBaseline] = useState<string | undefined>(undefined)

  const monitor = useMonitorDetail(id)
  const stats = useMonitorStats(id, period)
  const checkHistory = useCheckHistory(id, { pollUntilNewerThan: pollBaseline })
  const triggerCheck = useTriggerCheck(id)
  const deleteMonitor = useDeleteMonitor()

  const latestCheckedAt = checkHistory.data?.pages[0]?.results[0]?.checked_at
  const isWaitingForCheck =
    pollBaseline !== undefined && (!latestCheckedAt || latestCheckedAt <= pollBaseline)

  function handleCheckNow() {
    const baseline = latestCheckedAt ?? BEFORE_ANY_CHECK
    // The baseline is what makes the button say "Waiting for result…", and
    // only a newer check result clears it. Setting it before knowing the
    // request succeeded meant a refused trigger — throttled at 5/min, or a
    // paused monitor — left the button disabled on "Waiting" permanently,
    // since no check was ever queued to arrive and end the wait. Nothing
    // short of reloading the page recovered from it.
    triggerCheck.mutate(undefined, { onSuccess: () => setPollBaseline(baseline) })
  }

  function handleDelete() {
    deleteMonitor.mutate(id, { onSuccess: () => navigate('/dashboard', { replace: true }) })
  }

  // Each of these used to return bare markup with no window around it,
  // which left a stray line of text (or the whole edit form) floating in
  // the corner of the desktop instead of inside the page it belongs to.
  if (monitor.isLoading) {
    return (
      <PageLayout title="Monitor" size="compact">
        <p>Loading…</p>
      </PageLayout>
    )
  }
  if (monitor.isError || !monitor.data) {
    return (
      <PageLayout title="Monitor" size="compact">
        <p role="alert">Couldn't load this monitor.</p>
      </PageLayout>
    )
  }

  if (isEditing) {
    return (
      <PageLayout title={`Edit ${monitor.data.name}`}>
        <MonitorEditForm
          monitor={monitor.data}
          onSaved={() => setIsEditing(false)}
          onCancel={() => setIsEditing(false)}
        />
      </PageLayout>
    )
  }

  const m = monitor.data

  return (
    <PageLayout title={m.name}>
      <NavBar />

      <section>
        <StatusBadge status={m.status} />
        {m.open_incident_id && <OpenIncidentFlag />}
        {/* Only while a losing streak is under way and the monitor hasn't
            flipped yet. This is the window that otherwise looks like a bug:
            a check just failed, the status still reads UP, and nothing on
            the page explains that one more failure is what it takes. Once
            the status is DOWN the badge already says everything, and at
            zero there is no streak worth mentioning. */}
        {m.consecutive_failures > 0 && m.status !== 'DOWN' && (
          <p>
            Failing {m.consecutive_failures} of {m.failure_threshold} checks needed to open an
            incident
          </p>
        )}
        <p>{m.url}</p>
        <p>
          {m.method} · expects {m.expected_status} · every {m.interval_seconds}s · timeout{' '}
          {m.timeout_seconds}s
        </p>
        <p>
          Uptime (24h): {m.uptime_24h === null ? '—' : `${(m.uptime_24h * 100).toFixed(1)}%`} · Avg
          response (24h):{' '}
          {m.avg_response_time_24h_ms === null ? '—' : `${m.avg_response_time_24h_ms} ms`}
        </p>
        <Button onClick={() => setIsEditing(true)}>Edit</Button>
        {confirmingDelete ? (
          <>
            <span>Delete this monitor? This can't be undone.</span>
            <Button onClick={handleDelete} disabled={deleteMonitor.isPending}>
              {deleteMonitor.isPending ? 'Deleting…' : 'Confirm delete'}
            </Button>
            <Button onClick={() => setConfirmingDelete(false)}>Cancel</Button>
          </>
        ) : (
          <Button onClick={() => setConfirmingDelete(true)}>Delete</Button>
        )}
      </section>

      <section>
        <Button
          onClick={handleCheckNow}
          disabled={triggerCheck.isPending || isWaitingForCheck || !m.is_enabled}
        >
          {isWaitingForCheck ? 'Waiting for result…' : 'Check now'}
        </Button>
        {!m.is_enabled && <span>Paused — resume it from the dashboard to run checks.</span>}
        {triggerCheck.isError && <p role="alert">{describeCheckError(triggerCheck.error)}</p>}
      </section>

      <section>
        <label>
          Period
          <SelectNative
            options={PERIOD_OPTIONS}
            value={period}
            onChange={(option) => setPeriod(option.value as StatsPeriod)}
          />
        </label>
        {stats.isLoading && <p>Loading stats…</p>}
        {stats.data && (
          <>
            <p>{formatPeriodSummary(stats.data.summary)}</p>
            <StatsChart series={stats.data.series} />
          </>
        )}
      </section>

      <section>
        {checkHistory.isLoading && <p>Loading history…</p>}
        {checkHistory.data && (
          <CheckHistoryList
            checks={checkHistory.data.pages.flatMap((page) => page.results)}
            hasMore={checkHistory.hasNextPage}
            isLoadingMore={checkHistory.isFetchingNextPage}
            onLoadMore={() => checkHistory.fetchNextPage()}
          />
        )}
      </section>
    </PageLayout>
  )
}
