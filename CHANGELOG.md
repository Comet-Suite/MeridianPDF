# Changelog

## 5.0 — 2026-09

The biggest release yet.

### New
- **Direct Ink pen** — pen strokes are real vector ink, not thick pixels:
  - Pointer events are coalesced and smoothed, and stroke width follows your
    **speed and stylus pressure** — slow down and the nib swells; flick and
    it tapers.
  - Strokes stay crisp at any zoom and are baked with their variable widths
    into PDF exports; a lightweight preview layer keeps long strokes at
    drawing speed.
- **Ink-to-shape** — finish a rough line, rectangle, triangle or ellipse and
  it snaps into the perfect primitive (still a normal pen annotation, so
  erase / undo / export are untouched). Freehand writing is never affected,
  and the feature can be switched off in Settings → General → Pen.
- **Meridian Motion — camera gestures** — control the reader hands-free with
  a regular webcam, processed **entirely on-device** (no frame ever leaves
  the browser, no model is downloaded):
  - **Pinch** (closed hand) + move up/down → zoom in steps.
  - **Open-hand swipe** left/right → previous / next page.
  - **Open-palm hold** (1.2 s) → page down. **Fist hold** (1.8 s) → off.
  - First run **calibrates to your hand and lighting**; tracking then works
    across skin tones and dim or cool-light rooms (luminance auto-gain plus
    a tone-agnostic colour model), with a live signal meter, a draggable
    HUD, and Low/Medium/High sensitivity.
  - **Off by default** — enable in Settings → General → Camera control.
- **Command palette (`Ctrl`/`Cmd` + `K`)** — fuzzy-search every action, jump
  to any open tab, or type a page number like `12` and press Enter to go to
  page 12. Also on the Home command bar and in the header.
- **Edge-style Find** — every match is marked on the page as you type (not
  just the active one), with a **Match-case** toggle, ↑/↓ stepping, and a
  results drawer listing all matches by page with snippets.
- **Annotations panel** — the sidebar Comments tab becomes Annotations:
  live counts, Highlights / Notes / Ink filter chips, and per-mark delete.
- **Sharper OCR** — new *Enhance contrast & binarise* step (histogram
  stretch + Otsu threshold plus smart upscaling) for faint scans, interword
  spacing and layout-aware page segmentation, and per-page confidence.
- **Home & Welcome page** — the app opens onto a Home screen with quick
  actions and a **Recent documents** grid that tracks what you last worked on.
- **Multi-tab documents** — open any number of PDFs at once, each in its own
  tab; page, zoom, annotations, bookmarks and OCR state travel with every
  tab. Middle-click or ✕ to close.

### Changed
- **Meridian Console identity** — a refreshed look throughout: gradient
  action buttons, deeper glass surfaces, floating document tabs, an aurora
  Home header, and visible keyboard-focus rings.
- **New logo & icon set** — a redrawn meridian mark on the app icon,
  favicon, README strips and About, plus a bespoke two-line ("duoline")
  icon family across the toolbar, dock and menus.
- What's-new carousel and Home welcome banner written for 5.0.

### Refined in the same release
- **Print Center** — a redesigned print dialog with a live paper preview
  (paper size / orientation / grayscale), All / Current / Custom page
  scopes (`1-3, 7, 10-12`), and an Auto quality mode.
- **Edge-smooth input tools** — highlighting applies **while you drag**;
  the eraser deletes marks **instantly as it passes over them**, with
  frame-batched hit-testing.
- **Settings slimmed down** — Appearance keeps the essentials
  (accent colour, light/dark/system).

### Under the hood
- Live drag-highlighting uses a per-wrap **line-band cache**; pen ink stores
  per-point width multipliers (`dyn[]`) and OCR pages keep their confidence.
- Find/OCR text extraction is cached per page with a bounded, evicting
  cache so huge documents stay flat in memory.
- Single-file format unchanged — annotations from 4.x carry forward.

## 4.x

Earlier history predates this changelog.
