// The build prepends the cache version and the exact files emitted by Vite.
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) =>
      cache.addAll(
        SHELL_FILES.map(
          (url) =>
            new Request(url, {
              cache: "reload",
              credentials: "omit",
            }),
        ),
      ),
    ),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(
        names
          .filter(
            (name) => name.startsWith("sdu-map-shell-") && name !== SHELL_CACHE,
          )
          .map((name) => caches.delete(name)),
      );
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  if (request.mode === "navigate" && !url.pathname.startsWith("/api/")) {
    event.respondWith(
      (async () => {
        try {
          return await fetch(request);
        } catch {
          const cache = await caches.open(SHELL_CACHE);
          return (await cache.match("/index.html")) || Response.error();
        }
      })(),
    );
  } else if (SHELL_FILES.includes(url.pathname)) {
    event.respondWith(
      (async () => {
        const cache = await caches.open(SHELL_CACHE);
        return (await cache.match(url.pathname)) || fetch(request);
      })(),
    );
  }
});
