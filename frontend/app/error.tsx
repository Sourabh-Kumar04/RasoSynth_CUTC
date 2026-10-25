'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { AlertTriangle, RefreshCw, Home } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('Unhandled platform exception:', error)
  }, [error])

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white flex flex-col items-center justify-center p-6 font-mono text-center">
      <div className="w-16 h-16 rounded-2xl bg-rose-950/40 border border-rose-500/40 flex items-center justify-center mb-6 text-rose-400">
        <AlertTriangle className="w-8 h-8" />
      </div>
      <h1 className="text-xl font-bold text-white mb-2">Platform Exception Encountered</h1>
      <p className="text-xs text-[#94a3b8] max-w-md mb-6">
        An unexpected error occurred while rendering this view. Your persisted data in PostgreSQL and active synthesis jobs remain unaffected.
      </p>
      {error.message && (
        <div className="max-w-md p-3 mb-6 bg-[#12121a] border border-[#272738] rounded-md text-[11px] text-rose-300 text-left overflow-x-auto">
          <code>{error.message}</code>
        </div>
      )}
      <div className="flex items-center gap-3">
        <Button
          onClick={() => reset()}
          className="bg-[#f26625] hover:bg-[#de581a] text-white text-xs font-bold font-mono h-9 px-4 rounded-md flex items-center gap-2"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Retry Operation
        </Button>
        <Link href="/">
          <Button
            variant="outline"
            className="border-[#272738] bg-[#12121a] hover:bg-[#161622] text-white text-xs font-mono h-9 px-4 rounded-md flex items-center gap-2"
          >
            <Home className="w-3.5 h-3.5" />
            Return Home
          </Button>
        </Link>
      </div>
    </div>
  )
}
