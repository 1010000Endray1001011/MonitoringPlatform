import styled from 'styled-components'

// Functional color-coding, not the retro theme itself — a monitor that's
// DOWN needs to read as "wrong" at a glance regardless of what the
// eventual visual pass looks like, so these four colors exist now rather
// than waiting on that later pass.
const COLORS: Record<string, string> = {
  UP: '#0a7d1f',
  DOWN: '#b30000',
  PAUSED: '#6b6b6b',
  NEW: '#0033a0',
}

const Badge = styled.span<{ $color: string }>`
  display: inline-block;
  padding: 2px 8px;
  font-weight: bold;
  color: white;
  background-color: ${(props) => props.$color};
`

export function StatusBadge({ status }: { status: string }) {
  return <Badge $color={COLORS[status] ?? COLORS.NEW}>{status}</Badge>
}
