'use client';

import { useEffect, useState } from 'react';

/**
 * MockModeBanner renders synchronously on first paint via an inline script
 * that unhides #mock-mode-first-paint-banner if localStorage.mockMode === 'true'.
 *
 * This ensures the user sees:
 * "MOCK DATA — not live backend data"
 * immediately before any data loads or renders.
 */
export function MockModeBanner() {
  const [mounted, setMounted] = useState(false);
  const [isMock, setIsMock] = useState(false);

  useEffect(() => {
    setMounted(true);
    try {
      const active = localStorage.getItem('mockMode') === 'true';
      setIsMock(active);
    } catch {
      setIsMock(false);
    }
  }, []);

  return (
    <>
      {/* Synchronous first-paint banner container (toggled by inline script before paint) */}
      <div
        id="mock-mode-first-paint-banner"
        style={{ display: 'none' }}
        className="w-full bg-amber-500/20 border-b border-amber-500/50 px-4 py-2.5 text-center font-mono text-xs font-bold text-amber-300"
      >
        MOCK DATA — not live backend data
      </div>
      <script
        dangerouslySetInnerHTML={{
          __html: `
            try {
              if (typeof window !== 'undefined' && localStorage.getItem('mockMode') === 'true') {
                var el = document.getElementById('mock-mode-first-paint-banner');
                if (el) el.style.display = 'block';
              }
            } catch (e) {}
          `,
        }}
      />
    </>
  );
}
