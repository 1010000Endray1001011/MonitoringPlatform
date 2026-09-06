import { Button, GroupBox } from 'react95'
import styled from 'styled-components'
import type { MonitorList } from '../api/types'
import { OpenIncidentFlag } from './OpenIncidentFlag'
import { StatusBadge } from './StatusBadge'

const Row = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
`

const Url = styled.p`
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
`

interface MonitorCardProps {
  monitor: MonitorList
  onOpen: (id: string) => void
  onTogglePause: (monitor: MonitorList) => void
  isToggling: boolean
}

export function MonitorCard({ monitor, onOpen, onTogglePause, isToggling }: MonitorCardProps) {
  return (
    <GroupBox label={monitor.name}>
      <Row>
        <StatusBadge status={monitor.status} />
        {monitor.open_incident_id && <OpenIncidentFlag />}
      </Row>
      <Url title={monitor.url}>{monitor.url}</Url>
      <p>
        Last response:{' '}
        {monitor.last_response_time_ms === null ? '—' : `${monitor.last_response_time_ms} ms`}
      </p>
      <Row>
        <Button onClick={() => onOpen(monitor.id)}>Details</Button>
        <Button onClick={() => onTogglePause(monitor)} disabled={isToggling}>
          {monitor.is_enabled ? 'Pause' : 'Resume'}
        </Button>
      </Row>
    </GroupBox>
  )
}
