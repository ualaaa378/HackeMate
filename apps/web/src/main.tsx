import React from 'react';
import { createRoot } from 'react-dom/client';

import App from './App';
import { letraGuardada, ponerLetra } from './utils/letra';

ponerLetra(letraGuardada());

// PWA instalable (C4). Solo en producción: en desarrollo el service worker guardaría módulos de Vite.
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => void navigator.serviceWorker.register('/sw.js').catch(() => undefined));
}

const container = document.getElementById('root');
const root = createRoot(container!);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
