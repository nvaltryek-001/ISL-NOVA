import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { applyPrefs, prefs } from './lib/store';

applyPrefs(prefs.get());
createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
