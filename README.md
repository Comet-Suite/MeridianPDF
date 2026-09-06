<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/strip-dark.png">
    <img src="assets/strip-light.png" alt="Meridian PDF" width="420">
  </picture>
</p>

<h1 align="center">Meridian PDF</h1>

<p align="center">
  <b>A fast, private, multi-tab workspace for reading, annotating and organising PDFs — in a single HTML file.</b><br>
  No install. No account. No uploads. Your documents never leave your device.
</p>

<p align="center">
  ![version](https://img.shields.io/badge/version-5.0-5b5ce2) ![license](https://img.shields.io/badge/license-MIT-green) ![size](https://img.shields.io/badge/app-one%20file-ff9500) ![privacy](https://img.shields.io/badge/tracking-none-success)
</p>

---

## What is it?

Meridian PDF is a complete PDF reader and markup tool that lives in **one self-contained `index.html`**. Open it in any modern browser — desktop or phone — and you have a full document workspace: multi-tab reading, a Home screen with recent documents, highlights, notes, freehand pen, text overlays, OCR, form filling, digital signing, redaction, page organisation, and export to PDF/Word/PowerPoint/Excel/images.

The entire engine runs client-side (pdf.js + pdf-lib), so it works from a local file, a USB stick, or GitHub Pages — even on a plane.

## Version 5 highlights

| | |
|---|---|
| 🖊 **Direct Ink pen** | Strokes swell and taper with speed and stylus pressure — real vector ink instead of thick pixels, crisp at any zoom and in exports. |
| ✋ **Camera gestures** | Zoom, turn pages or scroll hands-free with a regular webcam. Calibrates to your hand and lighting, processed entirely on-device — no frame ever leaves the browser. Off by default. |
| ✏️ **Ink-to-shape** | Rough line, rectangle, triangle or ellipse → snaps into the perfect primitive. Freehand writing is never touched. |
| ⌨️ **Command palette** | `Ctrl`/`Cmd` + `K` fuzzy-searches every action, any open tab, and page numbers — type `12`, hit Enter, you're on page 12. |
| 🔎 **Edge-style Find** | All matches marked as you type, Match-case, ↑/↓ stepping, and a results drawer with snippets. |
| 🗂 **Annotations panel** | Counts, Highlights/Notes/Ink filters and one-click delete in the sidebar. |
| 🔍 **Sharper OCR** | Contrast enhancement + Otsu binarisation for faint scans, with per-page confidence. |
| 🎛 **Meridian Console identity** | Gradient actions, deeper glass, floating tab cards, a new logo and a bespoke duoline icon set. |
| 🏠 **Home & multi-tab workspace** | A real Home screen with recent documents, and any number of PDFs open at once — state travels with every tab. |
## Screenshots

**Home — every document in focus**
![Home screen](docs/screenshots/home.png)

**Multi-tab reading, Acrobat-style**
![Multiple document tabs](docs/screenshots/tabs.png)

**Recent documents, one click away**
![Home with recents](docs/screenshots/home-recents.png)

**Full annotation toolset**
![Reader with tools](docs/screenshots/reader.png)

**Works great on phones**
![Mobile](docs/screenshots/mobile-reader.png)

## Everything on board

- **Read** — continuous scroll, thumbnails, bookmarks, outline, per-document reading position, fit-to-width, pinch zoom
- **Annotate** — live drag highlighting (Edge-style), sticky notes with comments, freehand pressure pen (Direct Ink), instant eraser, editable text overlays, custom colors
- **OCR** — on-device text recognition for scanned pages, with contrast enhancement, a selectable text layer and searchable OCR PDF export
- **Hands-free** — optional webcam gestures (Meridian Motion): pinch to zoom, swipe to turn pages, palm to scroll — computed on-device, never uploaded
- **Organise** — rotate / reorder / delete / insert / extract pages; merge and split
- **Secure** — permanent redaction, document signing with cryptographic certificates, password-protected file support
- **Export** — annotated PDF (readable in Acrobat/Preview), flattened PDF, Word, PowerPoint, Excel, plain text, PNG archive
- **Print** — a Print Center with live paper preview, custom page ranges, and a full print preview with paper-size-aware layout
- **Comfort** — light/dark themes, accent colors, dockable toolbars, focus mode, keyboard shortcuts, `Ctrl`/`Cmd` + `K` command palette

## Run it

**Option 1 — one click:** download `index.html` and double-click it. That's the whole install.

**Option 2 — GitHub Pages:** visit the live deployment (see the About sidebar of this repo → *Website*).

> First launch fetches the pdf.js / pdf-lib engines from a CDN, so an internet connection is needed once. After that, the page can be used offline in most browsers via cache.

## Privacy

Meridian PDF has **no analytics, no telemetry, no network calls of its own**. Documents, annotations, bookmarks and OCR text are stored only in your browser's local storage, keyed per file. Nothing is ever uploaded. Camera gestures are strictly opt-in, and video frames are analysed in your browser's memory only — no frame is ever stored or transmitted.

## Tech

A single-file app built on [pdf.js](https://github.com/mozilla/pdf.js) (rendering) and [pdf-lib](https://github.com/Hopding/pdf-lib) (writing), with Tailwind for styling. The tab engine snapshots per-document state on switch, so memory stays flat no matter how many tabs are open; 5.0 adds a self-contained computer-vision layer (adaptive skin-tone blob tracking at 160×120, ~11 fps) that keeps camera gestures entirely off the network. See [OFFLINE.md](OFFLINE.md) for how the CDN engines could be bundled for a fully-offline single file.

## License

[MIT](LICENSE) © 2026 Comet-Suite
