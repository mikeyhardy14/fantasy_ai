"use client";

import { useSyncExternalStore } from "react";

/** Odds, spreads and prop prices stay out of the way unless someone asks for them. */
const KEY = "omaha.show-betting-lines";
const EVENT = "omaha:betting-lines";

export function readShowBettingLines(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function writeShowBettingLines(on: boolean): void {
  try {
    window.localStorage.setItem(KEY, on ? "1" : "0");
  } catch {
    // Private mode: the toggle still applies until the page reloads.
  }
  window.dispatchEvent(new Event(EVENT));
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function useShowBettingLines(): boolean {
  return useSyncExternalStore(subscribe, readShowBettingLines, () => false);
}
