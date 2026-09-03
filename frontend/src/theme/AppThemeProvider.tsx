import type { ReactNode } from 'react'
import { StyleSheetManager, ThemeProvider } from 'styled-components'
import isPropValid from '@emotion/is-prop-valid'
import original from 'react95/dist/themes/original'
import { GlobalStyles } from './GlobalStyles'

// React95's own components (Button, TextInput, ...) pass their custom
// styling props (active, primary, square, shadow, fullWidth, variant, ...)
// straight through to the underlying DOM element instead of consuming them
// — not a version mismatch with this app's React or styled-components,
// just how the library is built. isPropValid only forwards names that are
// real HTML/SVG attributes, which filters those out without needing to
// know react95's specific prop names ourselves.
export function AppThemeProvider({ children }: { children: ReactNode }) {
  return (
    <StyleSheetManager shouldForwardProp={isPropValid}>
      <ThemeProvider theme={original}>
        <GlobalStyles />
        {children}
      </ThemeProvider>
    </StyleSheetManager>
  )
}
