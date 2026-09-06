import styled from 'styled-components'
import { criticalGlow } from '../theme/criticalGlow'

// Functional color-coding, chosen in Chunk 8 before the theming pass and
// left as-is here — DOWN/UP/PAUSED/NEW already have good contrast against
// the white text they carry (verified during the Chunk 11 pass), so only
// the glow is new, not the colors themselves.
const COLORS: Record<string, string> = {
  UP: '#0a7d1f',
  DOWN: '#b30000',
  PAUSED: '#6b6b6b',
  NEW: '#0033a0',
}

const Badge = styled.span<{ $color: string; $critical: boolean }>`
  display: inline-block;
  padding: 2px 8px;
  font-weight: bold;
  color: white;
  background-color: ${(props) => props.$color};
  ${(props) => props.$critical && criticalGlow}
`

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge $color={COLORS[status] ?? COLORS.NEW} $critical={status === 'DOWN'}>
      {status}
    </Badge>
  )
}
