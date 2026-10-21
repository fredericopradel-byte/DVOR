# PDF.js local

- Upstream: Mozilla PDF.js (`pdfjs-dist`).
- Version: **4.10.38**, `legacy/build/pdf.mjs` and `legacy/build/pdf.worker.mjs`.
- Source: `https://unpkg.com/pdfjs-dist@4.10.38/`.
- License: Apache-2.0; complete license retained in `LICENSE`, with upstream notices in the bundles.
- No CDN dependency at runtime. The main service worker precaches both modules.
- The legacy build includes compatibility helpers. Real Safari/iOS validation remains required.
- Dynamic import happens only when opening a PDF. Images do not load PDF.js.
- Document JavaScript is not executed. `isEvalSupported` is false. Protected documents are rejected.
- The PDF.js canvas is an original-document preview; it is not the native editor or georeferenced output.
- Bundles are byte-for-byte upstream copies, including 12 generated lines with trailing whitespace.

SHA-256:

- `pdf.mjs`: `081d3b6f426d38a8029766f8839f505e9cbf2c81a71d62c26eada142e6c21ae4`
- `pdf.worker.mjs`: `5e9f76bd5e65fbd1602b29fc50e50490aeeacd34a715b2282b73f7e8029242e0`

The importer does not supply optional CMaps or standard-font files. The representative
charts use embedded fonts. Other documents may have missing glyphs or font substitutions;
successful parsing is not evidence of complete recognition. Image-only pages require an
OCR/vision provider, which is not included in stage 2.

When updating, review upstream advisories and the license, rerun real-chart and offline
tests, and update the main service-worker cache version. Do not replace these files with
remote imports.
