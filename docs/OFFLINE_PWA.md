# Installable app and offline use (PWA)

ISL NOVA can be installed from Chrome, Edge or Android ("Install app" / "Add to home screen") and keeps working when the network drops.

| Part | Behaviour |
|---|---|
| `manifest.webmanifest` | name, standalone display, theme colour, SVG + 512 px icon |
| `sw.js` (service worker) | caches the app shell (`/`, `/assets/*`, icons). SPA navigation is network-first and falls back to the cached shell offline |
| MediaPipe bundle, WASM and `.task` models | cached after the first online visit (cache-first), so the camera and hand tracking start offline |
| API calls (`/api/*`) | **never cached**: they carry personal data and live model state |
| Offline badge | shown in the header while the browser is offline |

**What works offline:** the interface, navigation, theme and language switching, and camera + hand tracking (after one online visit).

**What needs the server:** recognition (`/predict/sequence`), the vocabulary, login, practice scoring and all data.

Recognition runs on the server today. Fully offline recognition needs the in-browser (ONNX) model, which is planned but not yet implemented (see `V2_STATUS.md`).

The service worker registers only in a secure context (HTTPS or `localhost`/`127.0.0.1`).

**Tested:** the E2E test checks that the manifest is valid with a 512 px icon, that the service worker becomes ready, and that with the browser context offline the app shell still loads and shows the Offline badge.
