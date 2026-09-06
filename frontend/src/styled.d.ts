import type { Theme } from 'react95/dist/common/themes/types'
import 'styled-components'

// Without this, styled-components types the `theme` prop in `${({ theme
// }) => ...}` callbacks as an empty interface — this is the standard
// styled-components + react95 augmentation that makes `theme.<token>`
// actually type-check against react95's real theme shape (canvas,
// desktopBackground, headerBackground, ...).
declare module 'styled-components' {
  // The standard styled-components theme-augmentation shape — nothing to
  // add beyond react95's own Theme, hence the empty body.
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  export interface DefaultTheme extends Theme {}
}
