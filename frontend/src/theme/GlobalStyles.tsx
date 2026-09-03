import { createGlobalStyle } from 'styled-components'
import { styleReset } from 'react95'
import ms_sans_serif from 'react95/dist/fonts/ms_sans_serif.woff2'
import ms_sans_serif_bold from 'react95/dist/fonts/ms_sans_serif_bold.woff2'

// The actual retro theming (palette, cyberpunk accents) is a separate,
// later pass once every screen already exists — this is only the minimum
// React95 needs to render its components correctly at all: the CSS reset
// it ships with, and its own bitmap font (without it, every component
// still works, just in whatever the browser's default sans-serif is).
export const GlobalStyles = createGlobalStyle`
  ${styleReset}

  @font-face {
    font-family: 'ms_sans_serif';
    src: url('${ms_sans_serif}') format('woff2');
    font-weight: 400;
    font-style: normal;
  }
  @font-face {
    font-family: 'ms_sans_serif';
    src: url('${ms_sans_serif_bold}') format('woff2');
    font-weight: bold;
    font-style: normal;
  }

  body {
    font-family: 'ms_sans_serif';
  }
`
