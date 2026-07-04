"use client";

import { useEffect } from "react";

/**
 * Injects the Tailwind Play CDN script after React has fully hydrated and
 * committed. This avoids the hydration mismatch that `<Script strategy=…>`
 * caused (DOM modified before/during hydration → React couldn't attach event
 * handlers → nothing clickable).
 */
export function TailwindLoader() {
  useEffect(() => {
    if (document.querySelector('script[src*="cdn.tailwindcss.com"]')) return;
    const s = document.createElement("script");
    s.src = "https://cdn.tailwindcss.com";
    s.async = true;
    document.head.appendChild(s);
  }, []);
  return null;
}
