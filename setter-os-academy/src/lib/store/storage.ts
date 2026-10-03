"use client";
// Persistence adapter + tiny external store for React (useSyncExternalStore).
// Prototype: browser localStorage only. Nothing leaves the device.

import { useSyncExternalStore } from "react";
import { checkBackup, initialState, migrate, type AcademyState } from "./state";

export const STORAGE_KEY = "setter-os-academy:v1";
/** Safety copy: the raw state before an import, or unreadable data before a reset. Never overwritten silently. */
export const SAFETY_KEY = "setter-os-academy:safety";

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
    // corrupted storage: keep the raw text as a safety copy, then start fresh – never crash
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) window.localStorage.setItem(SAFETY_KEY, raw);
    } catch {
      /* blocked storage */
    }
    state = initialState();
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

/** Validates first; on any problem the current progress stays untouched and the reasons are thrown. */
export function importJson(text: string) {
  const check = checkBackup(text);
  if (!check.ok) throw new Error(check.problems.join(" "));
  const parsed = migrate(JSON.parse(text));
  try {
    window.localStorage.setItem(SAFETY_KEY, JSON.stringify(getState()));
  } catch {
    /* ignore */
  }
  update(() => parsed);
}

/** Restores the safety copy taken before the last import (undo). */
export function restoreSafetyCopy(): boolean {
  try {
    const raw = window.localStorage.getItem(SAFETY_KEY);
    if (!raw || !checkBackup(raw).ok) return false;
    const current = JSON.stringify(getState());
    update(() => migrate(JSON.parse(raw)));
    window.localStorage.setItem(SAFETY_KEY, current);
    return true;
  } catch {
    return false;
  }
}

export function hasSafetyCopy(): boolean {
  try {
    return !!window.localStorage.getItem(SAFETY_KEY);
  } catch {
    return false;
  }
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
