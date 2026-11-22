// Service worker de la PWA (C4). Solo guarda los estáticos de la web; /api/ y /webhook/ van siempre a la red.
const CACHE = 'hm-estaticos-v2'; // v2: iconos con el logo «Pueblos Unidos» (P2)

self.addEventListener('install', (ev) => {
  ev.waitUntil(caches.open(CACHE).then((c) => c.addAll(['/', '/manifest.json', '/favicon.png'])));
  self.skipWaiting();
});

self.addEventListener('activate', (ev) => {
  ev.waitUntil(
    caches
      .keys()
      .then((claves) => Promise.all(claves.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (ev) => {
  const url = new URL(ev.request.url);
  if (ev.request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/webhook/')) return;

  // Páginas: primero la red (para ver siempre la última versión) y, sin conexión, la copia guardada.
  if (ev.request.mode === 'navigate') {
    ev.respondWith(
      fetch(ev.request)
        .then((r) => {
          const copia = r.clone();
          caches.open(CACHE).then((c) => c.put('/', copia));
          return r;
        })
        .catch(() => caches.match('/')),
    );
    return;
  }

  // Estáticos (JS/CSS con hash, iconos, fotos): la copia guardada si existe; si no, la red y se guarda.
  ev.respondWith(
    caches.match(ev.request).then(
      (guardada) =>
        guardada ||
        fetch(ev.request).then((r) => {
          if (r.ok) {
            const copia = r.clone();
            caches.open(CACHE).then((c) => c.put(ev.request, copia));
          }
          return r;
        }),
    ),
  );
});
