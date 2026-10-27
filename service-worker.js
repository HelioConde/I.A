/* Brain-SSD / Luna static shell only. No conversations, models or user data are cached here. */
const CACHE_NAME = "luna-demo-static-v2";
const SHELL_FILES = ["./", "./index.html", "./styles.css", "./app.js", "./favicon.svg", "./manifest.webmanifest"];
const shellURLs = new Set(SHELL_FILES.map((file) => new URL(file, self.registration.scope).href));

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(SHELL_FILES))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((key) => key.startsWith("luna-demo-static-") && key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  const canonical = new URL(url.pathname, url.origin).href;
  const inScope = url.href.startsWith(self.registration.scope) && url.search === "";
  if (!inScope || !shellURLs.has(canonical)) return;

  event.respondWith((async () => {
    try {
      const response = await fetch(request);
      if (response.ok && response.type === "basic") {
        const cache = await caches.open(CACHE_NAME);
        await cache.put(request, response.clone());
      }
      return response;
    } catch {
      const cached = await caches.match(request,{ignoreSearch:true});
      return cached || Response.error();
    }
  })());
});
