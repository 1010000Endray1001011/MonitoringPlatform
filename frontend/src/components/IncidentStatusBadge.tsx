import styled from 'styled-components'
import type { IncidentStatus } from '../api/types'

// Same functional-color-first, theme-later reasoning as StatusBadge —
// amber for ACKNOWLEDGED sits deliberately between OPEN's red and
// RESOLVED's green, since "someone's aware of it" is neither "still
// actively bad" nor "over".
const COLORS: Record<IncidentStatus, string> = {
  OPEN: '#b30000',
  ACKNOWLEDGED: '#b8860b',
  RESOLVED: '#0a7d1f',
}

const Badge = styled.span<{ $color: string }>`
  display: inline-block;
  padding: 2px 8px;
  font-weight: bold;
  color: white;
  background-color: ${(props) => props.$color};
`

export function IncidentStatusBadge({ status }: { status: IncidentStatus }) {
  return <Badge $color={COLORS[status]}>{status}</Badge>
}
