const CACHE = 'bbm-v5';
const ASSETS = [
  '/fuelcalc/',
  '/fuelcalc/index.html',
  '/fuelcalc/manifest.json',
  '/fuelcalc/icon.svg',
  '/fuelcalc/tol.json',
  '/fuelcalc/harga.json'
];

self.addEventListener('install', e => {
  // Tidak skipWaiting otomatis — tunggu user klik "Perbarui"
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});

// Terima pesan dari app untuk skip waiting (tombol "Perbarui")
self.addEventListener('message', e => {
  if(e.data && e.data.type === 'SKIP_WAITING') self.skipWaiting();
});
