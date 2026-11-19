# Approved Reconcile assets

Source: `docs/screenshots/ChatGPT Image Nov 12, 2026, 09_14_34 PM.png` (retained unchanged).

The R, ascending bars and wordmark contours were traced from the supplied image into actual SVG
paths, including the wordmark's letter shapes. They contain no embedded raster images, substitute
font or white background rectangle. Raster paper texture and lighting are intentionally omitted;
the original reference remains authoritative for the design. This is a silhouette tracing, not an
original designer's editable vector master.

- `reconcile-symbol.svg` / `reconcile-wordmark.svg`: Forest artwork for light surfaces; muted
  green bars preserve contrast.
- `reconcile-symbol-dark.svg` / `reconcile-wordmark-dark.svg`: Sage artwork for Forest surfaces,
  with muted Sage bars and the approved Citron accent. Used by the header.
- `app-icon.svg`: the same symbol with intentional Forest backing and generous padding.
- `../favicon.svg`: transparent, padded symbol with adaptive Forest/Sage R for browser contrast.
- `../favicon-32.png`, `../apple-touch-icon.png`, `../app-icon-192.png`, `../app-icon-512.png`:
  raster exports of the app SVG for small-browser and installed-app use. These are PNGs, not vectors.
- `../site.webmanifest`: icon/name metadata only; no service worker or offline functionality.

The header's single accessible link name is “Reconcile Workbench home”; its decorative images
have empty alt text. The wordmark already says Reconcile, so only Workbench is typeset below it.
The same compact lockup is retained at 320px. No runtime background-removal CSS is used.
