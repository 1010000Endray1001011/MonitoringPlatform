import original from 'react95/dist/themes/original'
import type { Theme } from 'react95/dist/common/themes/types'

// Everything that makes a React95 window actually read as "Windows 95" —
// the 3D bevels, the grey chrome, the text colors — comes straight from
// react95's own `original` theme untouched (ADR-025: the component base
// isn't being redesigned here, only accented). The three tokens below are
// the deliberate "light cyberpunk" layer on top: the titlebar and the
// space behind the windows shift from stock Windows navy/teal toward a
// cyberpunk violet, which is the only theme-wide signal this pass adds —
// everything else (buttons, inputs, tables) stays exactly as Chunk 7–10
// already built it.
export const monitoringTheme: Theme = {
  ...original,
  headerBackground: '#1a0864',
  headerNotActiveBackground: '#4a3d6b',
  hoverBackground: '#1a0864',
  desktopBackground: '#0d0221',
  progress: '#1a0864',
}
