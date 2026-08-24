"use client";

import { useCallback, useMemo, useSyncExternalStore } from "react";

/**
 * localStorage-backed UI preference.
 *
 * localStorage is external mutable state, so it is read through
 * useSyncExternalStore rather than copied into state inside an effect: the
 * server snapshot is always the fallback, so the prerendered HTML matches, and
 * React swaps in the stored value on hydration without a mismatch.
 */

const listeners = new Set<() => void>();

function notify() {
  for (const listener of listeners) listener();
}

function subscribe(onStoreChange: () => void) {
  listeners.add(onStoreChange);
  // Keep other tabs in sync too.
  window.addEventListener("storage", onStoreChange);
  return () => {
    listeners.delete(onStoreChange);
    window.removeEventListener("storage", onStoreChange);
  };
}

export function usePersistedState<T>(
  key: string,
  fallback: T
): [T, (next: T) => void] {
  const getSnapshot = useCallback(() => {
    try {
      return window.localStorage.getItem(key);
    } catch {
      // Private mode or blocked storage.
      return null;
    }
  }, [key]);

  // Raw string keeps the snapshot referentially stable across renders.
  const raw = useSyncExternalStore(subscribe, getSnapshot, () => null);

  const value = useMemo(() => {
    if (raw === null) return fallback;
    try {
      return JSON.parse(raw) as T;
    } catch {
      return fallback;
    }
  }, [raw, fallback]);

  const setValue = useCallback(
    (next: T) => {
      try {
        window.localStorage.setItem(key, JSON.stringify(next));
      } catch {
        // Non-fatal — the preference just will not survive a reload.
      }
      notify();
    },
    [key]
  );

  return [value, setValue];
}
