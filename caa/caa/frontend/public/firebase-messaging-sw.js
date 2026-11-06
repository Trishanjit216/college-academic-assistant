// Receives phone push notifications while CAA is in the background or closed.
// It is separate from /sw.js (the offline/installable one) and uses its own scope, so the two never clash.
// The public Firebase settings arrive in this file's address (?apiKey=...), so no secret or setting is stored here.
importScripts(
  "https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js",
  "https://www.gstatic.com/firebasejs/10.14.1/firebase-messaging-compat.js"
);

const q = new URL(self.location.href).searchParams;
firebase.initializeApp({
  apiKey: q.get("apiKey"),
  projectId: q.get("projectId"),
  messagingSenderId: q.get("messagingSenderId"),
  appId: q.get("appId"),
});
const messaging = firebase.messaging();

// Only in-app paths may be opened from a notification.
const safeLink = (l) => (typeof l === "string" && l.startsWith("/") && !l.startsWith("//") && !l.includes("\\") ? l : "/notifications");

// Messages are data-only, and this is the ONLY place a visible notification is made for them (no duplicates).
// When CAA is open and visible, Firebase hands the message to the page instead and this does not run.
messaging.onBackgroundMessage((payload) => {
  const d = payload.data || {};
  if (!d.title) return;
  return self.registration.showNotification(d.title, {
    body: d.body || "",
    icon: "/icon-192.png",
    tag: d.tag || undefined,          // the same notification can never be shown twice
    data: { link: safeLink(d.link) },
  });
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = new URL(safeLink(event.notification.data && event.notification.data.link), self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(async (list) => {
      const open = list.find((c) => new URL(c.url).origin === self.location.origin);
      if (open) {
        try { await open.focus(); return await open.navigate(url); } catch (e) { /* fall through to a new window */ }
      }
      return self.clients.openWindow(url);
    })
  );
});
