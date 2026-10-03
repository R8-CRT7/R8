"use client";
// Persistence adapter + tiny external store for React (useSyncExternalStore).
// Prototype: browser localStorage only. Nothing leaves the device.

import { useSyncExternalStore } from "react";
import { initialState, migrate, type AcademyState } from "./state";

export const STORAGE_KEY = "setter-os-academy:v1";

let state: AcademyState = initialState();
let loaded = false;
const listeners = new Set<() => void>();

function load() {
  if (loaded || typeof window === "undefined") return;
  loaded = true;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    state = raw ? migrate(JSON.parse(raw)) : initialState();
  } catch {
    state = initialState(); // corrupted or blocked storage: start fresh, never crash
  }
}

function persist() {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* storage full or blocked (private mode) – app keeps working in memory */
  }
}

export function getState(): AcademyState {
  load();
  return state;
}

export function update(fn: (s: AcademyState) => AcademyState) {
  load();
  state = fn(state);
  persist();
  listeners.forEach((l) => l());
}

export function resetAll() {
  state = initialState();
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
  listeners.forEach((l) => l());
}

export function exportJson(): string {
  return JSON.stringify(getState(), null, 2);
}

export function importJson(text: string) {
  const parsed = migrate(JSON.parse(text));
  update(() => parsed);
}

function subscribe(l: () => void) {
  listeners.add(l);
  const onStorage = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY) {
      loaded = false;
      load();
      l();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(l);
    window.removeEventListener("storage", onStorage);
  };
}

const serverSnapshot = initialState();

export function useAcademy(): AcademyState {
  return useSyncExternalStore(subscribe, getState, () => serverSnapshot);
}

/** True after hydration – avoids flashing "no profile" content during static render. */
export function useHydrated(): boolean {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}
