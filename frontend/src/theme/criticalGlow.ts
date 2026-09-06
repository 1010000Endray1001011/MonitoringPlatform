import { css, keyframes } from 'styled-components'

const pulse = keyframes`
  0%, 100% {
    box-shadow: 0 0 4px #ff2e97, 0 0 10px #00fff2;
  }
  50% {
    box-shadow: 0 0 8px #ff2e97, 0 0 18px #00fff2;
  }
`

// Reserved for exactly the two states the ROADMAP calls out by name — a
// monitor that's DOWN, an incident that's OPEN — not applied to every
// alert or badge. If everything glows, the glow stops meaning "this needs
// you," which is the entire point of adding it in an otherwise plain
// Win95 theme (ADR-025). Purely a box-shadow, not a text/background color
// change, so it never affects the WCAG contrast of the text it surrounds.
export const criticalGlow = css`
  animation: ${pulse} 1.6s ease-in-out infinite;
`
