# Making Meridian PDF fully offline

**Status: plan / design document — deliberately not implemented yet.**

Meridian PDF is a single HTML file whose *features* all run locally
(rendering, annotation, tabs, gestures, even the print pipeline). The only
network touchpoints today are third-party **libraries and assets** fetched
from CDNs on demand:

| Asset | CDN today | Needed for |
|---|---|---|
| `pdf.js` + worker (`pdf.min.js`, `pdf.worker.min.js`) | cdnjs | rendering every PDF |
| cMaps + standard fonts (`cmaps/`, `standard_fonts/`) | cdnjs | CJK text & the 14 standard fonts |
| `pdf-lib.min.js` | cdnjs | saving / exporting PDFs |
| `tesseract.min.js` + WASM core + `*.traineddata` language files | jsDelivr | OCR |
| Tailwind browser build (`@tailwindcss/browser@4`) | jsDelivr | styling (the app already renders without it, but styled correctly only with it) |

Until these are local, first launch requires internet. Below are three ways
to remove that dependency, cheapest first.

---

## Strategy A — Inline everything into the single HTML file (recommended)

One build step produces `MeridianPDF-Offline.html` with **zero** network
dependencies.

1. **Vendor the libraries.** Download once at build time:
   `pdf.min.js`, `pdf.worker.min.js`, `pdf-lib.min.js`, `tesseract.min.js`,
   Tailwind's compiled CSS (or replace Tailwind with a small precompiled
   stylesheet of only the classes the app uses).
2. **Inline the scripts.** Replace the `<script src=…>` tags with inline
   `<script>` blocks containing the file contents. pdf.js works inlined; only
   its *worker* must be a separate script context. Two options:
   ```js
   // Option 1: worker from a Blob URL (keeps rendering off the main thread)
   const workerCode = `…contents of pdf.worker.min.js…`;   // inlined as a JS string
   pdfjsLib.GlobalWorkerOptions.workerSrc =
     URL.createObjectURL(new Blob([workerCode], { type: 'application/javascript' }));

   // Option 2 (fallback): disable the worker entirely — rendering runs on the
   // main thread. Simpler, slightly less smooth on very large PDFs.
   pdfjsLib.GlobalWorkerOptions.workerSrc = false;
   ```
3. **Fonts & cMaps.** This is the only genuinely awkward part:
   - *Standard 14 fonts*: `standard_fonts/` is ~1.4 MB — base64-inline the
     .pfb files and register a `DataRange`-style custom
     `standardFontDataUrl` (pdf.js accepts a `useSystemFonts:true` option
     which covers most documents; inline the folder for full fidelity).
   - *cMaps* (needed for some CJK/legacy encodings): the full set is ~6 MB.
     Either inline the ~40 most common (`GBK-EUC-H`, `UniGB-UCS2-H`, …) as
     base64 and serve via a custom `CMapReaderFactory`, or accept the
     graceful degradation for rare encodings.
4. **Tesseract assets.** The WASM core (~3 MB) and each language's
   `traineddata.gz` (`eng` ≈ 11 MB, `hin` ≈ 6 MB…) are the heavy items:
   - point `workerPath` / `corePath` / `langPath` at same-package local
     copies, **or**
   - inline the core, and let Tesseract's `cacheMethod:'indexedDB'` persist
     language data after the user first adds it (ship an "OCR language pack"
     flow in Settings: pick a language → one-time fetch → cached forever).
5. **Camera gestures need nothing** — the Meridian Motion engine is
   already model-free and 100 % local by design.

**Size estimate:** app (≈0.8 MB) + pdf.js pair (≈1.4 MB) + pdf-lib (≈0.5 MB)
+ Tailwind CSS (≈0.1 MB) ≈ **2.8 MB single file**, before OCR assets.
With `eng.traineddata` inlined it grows to ≈ 14 MB — which is why OCR is
better shipped as an optional pack (Strategy A2) than fully inlined.

**Build script sketch** (add as `tools/build-offline.py`):

```
fetch each CDN asset (pin exact versions!)
inline <script src> → <script>…</script>
inline worker  → JS string + Blob URL
inline tesseract core → same
optionally: inline base64 font/cmap packs + patch the two URL constants
write MeridianPDF-Offline.html
```

## Strategy B — PWA / Service Worker (best for hosted use)

For the GitHub Pages deployment, add a tiny service worker + web manifest:

- `manifest.webmanifest` (name, icons — the logo already exists in `/assets`)
- `sw.js` with a *cache-first* strategy for the app shell **and** the CDN
  assets (opaque-cached at first load): after one online visit the app opens
  and works with the network cable pulled.
- OCR language files get cached the same way on first OCR use.
- Caveat: service workers require HTTPS (Pages qualifies) and do nothing for
  `file://` double-click use.

This also makes the app **installable** (desktop/Android "Add to home
screen"), which pairs well with the offline claim.

## Strategy C — Desktop shell (Electron/Tauri)

The codebase already contains an Electron bridge (`Bridge`, printers,
file-association). Packaging with Electron (or Tauri, far smaller) bundles
every asset into the executable: fully offline by construction, plus real
printing and file associations. Highest effort, best desktop story.

## Recommendation

1. Ship **Strategy B now** (small, makes Pages installs offline + PWA).
2. Add a **build-time inliner** (Strategy A) to release
   `MeridianPDF-Offline.html` for the double-click/no-server audience.
3. Keep OCR language data as an opt-in one-time download (A2) rather than
   bloating the file by ~11 MB per language.
