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
// this pass introduces). Three layers sit on top of it, and the order
// matters: CSS paints the first-listed background-image nearest the
// viewer, so the two grid gradients are listed first and the glow last,
// leaving the grid lines visible *over* the lit area rather than being
// washed out by it.
//
// The grid is deliberately fine and faint. An earlier, coarser version
// (40px cells at ~6% opacity) read as unfinished placeholder checkering
// rather than as texture; halving the cell size and dropping the opacity
// turns it back into something the eye registers as surface rather than
// as content. The radial glow underneath is what actually fixes the
// emptiness: it puts a pool of light where the centered content sits, so
// a screen holding a single dialog looks composed instead of abandoned.
//
// background-attachment: fixed anchors all three layers to the viewport
// rather than the document, so the glow stays centered behind the content
// on a long scrolling page (the dashboard) instead of sliding off the top.
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
        rgba(0, 255, 242, 0.035) 0px,
        rgba(0, 255, 242, 0.035) 1px,
        transparent 1px,
        transparent 22px
      ),
      repeating-linear-gradient(
        90deg,
        rgba(0, 255, 242, 0.035) 0px,
        rgba(0, 255, 242, 0.035) 1px,
        transparent 1px,
        transparent 22px
      ),
      radial-gradient(
        ellipse 85% 65% at 50% 42%,
        rgba(103, 58, 183, 0.5) 0%,
        rgba(26, 8, 100, 0.28) 45%,
        rgba(13, 2, 33, 0) 78%
      );
    background-attachment: fixed;
  }
`
