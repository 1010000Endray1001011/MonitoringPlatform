import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, TextInput } from 'react95'
import styled from 'styled-components'
import { useMonitors, usePauseMonitor, useResumeMonitor } from '../api/monitors'
import type { MonitorList } from '../api/types'
import { CreateMonitorForm } from '../components/CreateMonitorForm'
import { MonitorCard } from '../components/MonitorCard'
import { NavBar } from '../components/NavBar'
import { PageLayout } from '../components/PageLayout'

// Fires the search request 300ms after the user stops typing rather than
// on every keystroke — the backend's search filter is cheap, but there's
// nothing to gain from a fresh request per character either.
function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}

const Toolbar = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`

// Takes whatever width the button beside it doesn't need, rather than
// react95's default fixed input width, which looked lost in a window this
// wide.
const SearchField = styled(TextInput)`
  flex: 1;
`

export function DashboardPage() {
  const navigate = useNavigate()
  const [searchInput, setSearchInput] = useState('')
  const [showCreateForm, setShowCreateForm] = useState(false)
  const search = useDebouncedValue(searchInput, 300)

  const monitors = useMonitors({ search: search || undefined })
  const pauseMonitor = usePauseMonitor()
  const resumeMonitor = useResumeMonitor()

  function handleTogglePause(monitor: MonitorList) {
    if (monitor.is_enabled) {
      pauseMonitor.mutate(monitor.id)
    } else {
      resumeMonitor.mutate(monitor.id)
    }
  }

  function isToggling(id: string): boolean {
    return (
      (pauseMonitor.isPending && pauseMonitor.variables === id) ||
      (resumeMonitor.isPending && resumeMonitor.variables === id)
    )
  }

  return (
    <PageLayout title="Dashboard">
      <NavBar />

      {showCreateForm ? (
        <CreateMonitorForm
          onCreated={() => setShowCreateForm(false)}
          onCancel={() => setShowCreateForm(false)}
        />
      ) : (
        <>
          <Toolbar>
            <SearchField
              placeholder="Search monitors"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
            />
            <Button onClick={() => setShowCreateForm(true)}>New monitor</Button>
          </Toolbar>

          {monitors.isLoading && <p>Loading…</p>}
          {monitors.isError && <p role="alert">Couldn't load your monitors. Try reloading.</p>}

          {monitors.data && monitors.data.results.length === 0 && (
            <p>
              {search
                ? 'No monitors match your search.'
                : "You don't have any monitors yet — create your first one to start tracking uptime."}
            </p>
          )}

          {monitors.data?.results.map((monitor) => (
            <MonitorCard
              key={monitor.id}
              monitor={monitor}
              onOpen={(id) => navigate(`/monitors/${id}`)}
              onTogglePause={handleTogglePause}
              isToggling={isToggling(monitor.id)}
            />
          ))}
        </>
      )}
    </PageLayout>
  )
}
