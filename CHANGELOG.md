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

### Under the hood
- `loadPdf()` accepts a per-tab resume state and aborts stale loads when the
  user switches tabs mid-parse.
- `goToPage()` now keeps the page counter in sync immediately.
- Per-document storage format unchanged — files you annotated in 4.x keep
  their marks, bookmarks and OCR text.

## 4.x

Earlier history predates this changelog.
