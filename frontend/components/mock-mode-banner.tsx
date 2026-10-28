'use client';

import { useEffect, useState } from 'react';

// Shown on every page while this browser serves mock data (localStorage
// mockMode === 'true'), so mock payloads can never read as live results.
export function MockModeBanner() {
  const [isMock, setIsMock] = useState(false);

  useEffect(() => {
    try {
      setIsMock(localStorage.getItem('mockMode') === 'true');
    } catch {
      setIsMock(false);
    }
  }, []);

  if (!isMock) return null;

  return (
    <div className="w-full bg-amber-500/15 border-b border-amber-500/40 px-4 py-2 text-center font-mono text-[11px] text-amber-300">
      MOCK MODE — this browser is serving demo/mock data, not live results. Remove the mockMode flag from this browser&apos;s local storage to return to live data.
    </div>
  );
}
