import styled from 'styled-components'
import { criticalGlow } from '../theme/criticalGlow'

// Was two different, inconsistent treatments before this pass — plain
// bold red text on MonitorCard, unstyled default text on
// MonitorDetailPage. Same signal, same component now: white-on-red like
// the other status badges (already verified for contrast there) plus the
// glow, since an open incident is exactly the kind of "needs you" state
// the glow exists for.
const Flag = styled.span`
  display: inline-block;
  padding: 2px 8px;
  font-weight: bold;
  color: white;
  background-color: #b30000;
  ${criticalGlow}
`

export function OpenIncidentFlag() {
  return <Flag role="alert">⚠ Open incident</Flag>
}
