import styled from 'styled-components'
import type { IncidentStatus } from '../api/types'
import { criticalGlow } from '../theme/criticalGlow'

// Same functional-color-first reasoning as StatusBadge — amber for
// ACKNOWLEDGED sits deliberately between OPEN's red and RESOLVED's green,
// since "someone's aware of it" is neither "still actively bad" nor
// "over". The amber is darker than a first pass would pick (`#b8860b`,
// standard CSS "darkgoldenrod") because that shade only clears ~3.3:1
// contrast against the white badge text — enough for large bold text but
// not WCAG AA's 4.5:1 floor for normal text; `#8a6508` clears ~5.4:1.
const COLORS: Record<IncidentStatus, string> = {
  OPEN: '#b30000',
  ACKNOWLEDGED: '#8a6508',
  RESOLVED: '#0a7d1f',
}

const Badge = styled.span<{ $color: string; $critical: boolean }>`
  display: inline-block;
  padding: 2px 8px;
  font-weight: bold;
  color: white;
  background-color: ${(props) => props.$color};
  ${(props) => props.$critical && criticalGlow}
`

export function IncidentStatusBadge({ status }: { status: IncidentStatus }) {
  return (
    <Badge $color={COLORS[status]} $critical={status === 'OPEN'}>
      {status}
    </Badge>
  )
}
