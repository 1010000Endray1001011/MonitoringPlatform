import { createGlobalStyle } from 'styled-components'
import { styleReset } from 'react95'
import ms_sans_serif from 'react95/dist/fonts/ms_sans_serif.woff2'
import ms_sans_serif_bold from 'react95/dist/fonts/ms_sans_serif_bold.woff2'

// styleReset + the bitmap font are what React95 needs to render its
// components correctly at all — unrelated to the theming pass below, just
// grouped in the same file since both are truly global CSS.
//
// The body background is the "desktop" a Win95 window normally floats on
// (real Windows used a flat teal here — `theme.desktopBackground` still
// exists as that same token, just repurposed toward the cyberpunk violet
// this pass introduces). The two repeating-linear-gradients on top of it
// are a faint cyan grid — cheap to do in CSS, and it reads as "cyberpunk
// desktop" without building an actual desktop-icons/taskbar metaphor,
// which ADR-025 / the ROADMAP's cut-list explicitly leave optional.
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
    min-height: 100vh;
    background-color: ${({ theme }) => theme.desktopBackground};
    background-image:
      repeating-linear-gradient(
        0deg,
        rgba(0, 255, 242, 0.06) 0px,
        rgba(0, 255, 242, 0.06) 1px,
        transparent 1px,
        transparent 40px
      ),
      repeating-linear-gradient(
        90deg,
        rgba(0, 255, 242, 0.06) 0px,
        rgba(0, 255, 242, 0.06) 1px,
        transparent 1px,
        transparent 40px
      );
  }
`
