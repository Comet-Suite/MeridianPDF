# Changelog

## 5.0 — 2026-09

The biggest release yet.

### New
- **Home & Welcome page** — the app now opens onto a Home screen with quick actions
  (open a file, blank PDF, tools), a first-run welcome banner, and a
  **Recent documents** grid that tracks what you last worked on.
- **Multi-tab documents** — open any number of PDFs at once, each in its own tab.
  - Switching tabs preserves each document's page, zoom, annotations, bookmarks,
    OCR results and page rotations.
  - The browser tab title follows the active document.
  - Close with the tab's ✕ or a middle-click; the neighbour tab takes over.
- **New identity** — new logo and icon across the app; the application name now
  appears only in the About window.
- **What's new carousel** rewritten for version 5 with fresh artwork.

### Changed
- Recent documents remember page counts and open/closed state.
- Zoom controls stay out of the way while no document is open.
- Cleaner, quieter UI copy throughout.

### Refined in the same release
- **Print Center** — a redesigned print dialog with a live paper preview that
  mirrors paper size / orientation / grayscale in real time, All / Current /
  Custom page scopes (ranges like `1-3, 7, 10-12`), and an Auto quality mode.
- **Edge-smooth input tools** —
  - Highlighting now applies **while you drag** (live caret-geometry
    highlighting, exactly like the Edge PDF viewer) instead of committing
    only after release.
  - The eraser deletes marks **instantly as it passes over them**, with
    frame-batched hit-testing and a per-drag geometry cache, so long
    documents scrub smoothly.
- **Settings slimmed down** — icon theme / icon colour / icon animation
  customisation removed; Appearance now holds the essentials (accent colour,
  light/dark/system).

### Under the hood
- `loadPdf()` accepts a per-tab resume state and aborts stale loads when the
  user switches tabs mid-parse.
- `goToPage()` now keeps the page counter in sync immediately.
- Per-document storage format unchanged — files you annotated in 4.x keep
  their marks, bookmarks and OCR text.

## 4.x

Earlier history predates this changelog.
