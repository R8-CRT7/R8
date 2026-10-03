// In-memory router for the single-file build (claude.ai artifact). Replaces Next.js routing.
import { useSyncExternalStore } from "react";

let path = "/";
const listeners = new Set<() => void>();
const history: string[] = [];

export function normalize(p: string): string {
  const [base = "/", q] = p.split("?");
  let b = base.startsWith("/") ? base : `/${base}`;
  if (!b.endsWith("/")) b += "/";
  return q ? `${b}?${q}` : b;
}

export function navigate(to: string, replace = false) {
  const next = normalize(to);
  if (!replace) history.push(path);
  path = next;
  try { window.scrollTo({ top: 0 }); } catch { /* ignore */ }
  listeners.forEach((l) => l());
}

export function back() {
  const prev = history.pop();
  if (prev) {
    path = prev;
    listeners.forEach((l) => l());
  }
}

export function setInitial(p: string) {
  path = normalize(p);
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};
export function useLocation(): string {
  return useSyncExternalStore(subscribe, () => path, () => path);
}
