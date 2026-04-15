/* SocialPoster Service Worker */

var CACHE_NAME = 'socialposter-v1';
var STATIC_ASSETS = [
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/offline.html'
];

// Install – pre-cache static assets (skip failures)
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      // Try to cache each asset individually, skip failures
      return Promise.all(
        STATIC_ASSETS.map(function(url) {
          return fetch(url).then(function(response) {
            if (response.ok) {
              return cache.put(url, response);
            }
          }).catch(function() {
            // Silently skip failed assets
          });
        })
      );
    })
  );
  self.skipWaiting();
});

// Activate – clean up old caches
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(key) {
          return key !== CACHE_NAME;
        }).map(function(key) {
          return caches.delete(key);
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch – cache-first for static, network-first for navigation
self.addEventListener('fetch', function(event) {
  var url = new URL(event.request.url);

  // Cache-first for static assets
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then(function(cached) {
        return cached || fetch(event.request).then(function(response) {
          if (response && response.ok) {
            var clone = response.clone();
            caches.open(CACHE_NAME).then(function(cache) {
              cache.put(event.request, clone);
            });
          }
          return response;
        }).catch(function() {
          // Return a cached response if available, otherwise return a blank response
          return cached || new Response('', { status: 404 });
        });
      })
    );
    return;
  }

  // Network-first for navigation (HTML pages)
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .then(function(response) {
          // Cache successful responses
          if (response && response.ok) {
            var clone = response.clone();
            caches.open(CACHE_NAME).then(function(cache) {
              cache.put(event.request, clone);
            });
          }
          return response;
        })
        .catch(function() {
          // When offline, try to return cached version
          return caches.match(event.request).then(function(cached) {
            return cached || fetch('/offline.html').catch(function() {
              return new Response('Offline', { status: 503 });
            });
          });
        })
    );
    return;
  }

  // Default: network with cache fallback
  event.respondWith(
    fetch(event.request)
      .then(function(response) {
        if (response && response.ok && event.request.method === 'GET') {
          var clone = response.clone();
          caches.open(CACHE_NAME).then(function(cache) {
            cache.put(event.request, clone);
          });
        }
        return response;
      })
      .catch(function() {
        return caches.match(event.request) || new Response('', { status: 404 });
      })
  );
});
