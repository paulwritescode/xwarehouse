self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("push", (event) => { const data = event.data ? event.data.json() : { title: "XWarehouse summary ready", body: "Your administrator call summary is ready." }; event.waitUntil(self.registration.showNotification(data.title, { body: data.body, icon: "/assets/electronics/warehouse-pwa/icon.svg", data: { url: "/app/warehouse-call" } })); });
self.addEventListener("notificationclick", (event) => { event.notification.close(); event.waitUntil(clients.openWindow((event.notification.data && event.notification.data.url) || "/app/warehouse-call")); });
