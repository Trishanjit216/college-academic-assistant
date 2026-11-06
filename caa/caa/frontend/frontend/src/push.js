// Browser side of phone push (Firebase Cloud Messaging). Nothing secret lives here: these Firebase web settings are public by design.
// The firebase library is loaded only when someone actually uses push, so it costs everyone else nothing.
import { api } from "./api.js";

const env = import.meta.env;
const CFG = {
  apiKey: env.VITE_FIREBASE_API_KEY, projectId: env.VITE_FIREBASE_PROJECT_ID,
  messagingSenderId: env.VITE_FIREBASE_MESSAGING_SENDER_ID, appId: env.VITE_FIREBASE_APP_ID,
};
const VAPID = env.VITE_FIREBASE_VAPID_KEY;
const KEY = "caa-push-token";
const SW_URL = "/firebase-messaging-sw.js";
const SW_SCOPE = "/firebase-cloud-messaging-push-scope";

const mem = (() => { const o = {}; return { get: (k) => o[k] || null, set: (k, v) => { o[k] = v; }, del: (k) => { delete o[k]; } }; })();
const store = {
  get: (k) => { try { return localStorage.getItem(k); } catch { return mem.get(k); } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch { mem.set(k, v); } },
  del: (k) => { try { localStorage.removeItem(k); } catch { mem.del(k); } },
};

export class PushError extends Error {
  constructor(code, message) { super(message); this.code = code; }
}

export const firebaseConfigured = () => !!(CFG.apiKey && CFG.projectId && CFG.messagingSenderId && CFG.appId && VAPID);
export const savedToken = () => store.get(KEY);
export const permission = () => (typeof Notification === "undefined" ? "unsupported" : Notification.permission);

/** {ok:true} or {ok:false, reason} written for a student, not a developer. */
export function browserSupport() {
  const ua = navigator.userAgent || "";
  const ios = /iPhone|iPad|iPod/.test(ua);
  const standalone = window.matchMedia?.("(display-mode: standalone)").matches || navigator.standalone;
  if (ios && !standalone) return { ok: false, reason: "On iPhone, first add CAA to your Home Screen (Share → Add to Home Screen) and open it from there. Then come back here." };
  if (!window.isSecureContext) return { ok: false, reason: "Phone notifications need a secure (https) connection." };
  if (!("serviceWorker" in navigator) || !("PushManager" in window) || typeof Notification === "undefined")
    return { ok: false, reason: "This browser can't receive phone notifications. Try Chrome on Android." };
  return { ok: true };
}

async function messagingApi() {
  const [app, msg] = await Promise.all([import("firebase/app"), import("firebase/messaging")]);
  if (!(await msg.isSupported())) throw new PushError("unsupported", "This browser can't receive phone notifications. Try Chrome on Android.");
  const instance = app.getApps()[0] || app.initializeApp(CFG);
  return { messaging: msg.getMessaging(instance), msg };
}

async function tokenFor(messaging, msg) {
  const reg = await navigator.serviceWorker.register(`${SW_URL}?${new URLSearchParams(CFG)}`, { scope: SW_SCOPE });
  const token = await msg.getToken(messaging, { vapidKey: VAPID, serviceWorkerRegistration: reg });
  if (!token) throw new PushError("no_token", "Your phone didn't give us a notification address. Please try again.");
  return token;
}

/** Called only from a button tap. Asks permission, registers the device, tells the server. */
export async function enablePush() {
  const s = browserSupport();
  if (!s.ok) throw new PushError("unsupported", s.reason);
  if (!firebaseConfigured()) throw new PushError("not_configured", "Phone notifications aren't switched on for this site yet.");
  if (Notification.permission === "denied") throw new PushError("denied", "Notifications are blocked for this site in your browser settings.");
  const result = await Notification.requestPermission();
  if (result !== "granted") throw new PushError(result === "denied" ? "denied" : "dismissed", result === "denied" ? "Notifications are blocked for this site in your browser settings." : "You didn't allow notifications, so nothing was turned on.");
  let token;
  try {
    const { messaging, msg } = await messagingApi();
    token = await tokenFor(messaging, msg);
  } catch (e) {
    if (e instanceof PushError) throw e;
    throw new PushError("register_failed", "Couldn't register this phone for notifications. Check your connection and try again.");
  }
  await api("/push/register/", { method: "POST", body: { token } });
  store.set(KEY, token);
  return token;
}

/** Turn off on this phone: tell the server, forget the token, release it at Firebase. */
export async function disablePush() {
  const token = store.get(KEY);
  store.del(KEY);
  if (token) await api("/push/unregister/", { method: "POST", body: { token } }).catch(() => {});
  try { const { messaging, msg } = await messagingApi(); await msg.deleteToken(messaging); } catch { /* already gone */ }
}

/** On logout: stop alerts for this account on this phone (best effort, short wait). */
export async function leaveDevice() {
  const token = store.get(KEY);
  if (!token) return;
  store.del(KEY);
  await Promise.race([api("/push/unregister/", { method: "POST", body: { token } }).catch(() => {}), new Promise((r) => setTimeout(r, 1500))]);
}

/** Quietly keep the server in step: tokens rotate, permission can be revoked in browser settings. Never prompts. */
export async function syncPush() {
  const token = store.get(KEY);
  if (!token) return "off";
  if (permission() !== "granted" || !firebaseConfigured()) {
    await api("/push/unregister/", { method: "POST", body: { token } }).catch(() => {});
    store.del(KEY);
    return "off";
  }
  try {
    const { messaging, msg } = await messagingApi();
    const fresh = await tokenFor(messaging, msg);
    if (fresh !== token) { await api("/push/register/", { method: "POST", body: { token: fresh } }); store.set(KEY, fresh); }
  } catch { /* offline or transient: keep what we have */ }
  return "on";
}

/** Messages that arrive while CAA is open and visible. Returns an unsubscribe function. */
export async function listenForeground(cb) {
  const { messaging, msg } = await messagingApi();
  return msg.onMessage(messaging, (payload) => cb(payload.data || {}));
}
