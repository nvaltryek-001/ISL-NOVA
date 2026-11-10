import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { applyPrefs, prefs } from './lib/store';

applyPrefs(prefs.get());
createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);

// Offline support (PWA): cache the app shell and the MediaPipe assets after the first online visit.
if ('serviceWorker' in navigator && window.isSecureContext) {
  window.addEventListener('load', () => { navigator.serviceWorker.register('/sw.js').catch(() => { /* optional */ }); });
}
