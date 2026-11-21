import React from 'react';
import { createRoot } from 'react-dom/client';

import App from './App';
import { letraGuardada, ponerLetra } from './utils/letra';

ponerLetra(letraGuardada());

const container = document.getElementById('root');
const root = createRoot(container!);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
