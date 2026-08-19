'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, useEffect } from 'react'

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30 * 1000, // 30 seconds
            gcTime: 5 * 60 * 1000, // 5 minutes
            retry: 2,
            refetchOnWindowFocus: false,
          },
        },
      })
  )

  // Auto-reload on ChunkLoadError caused by fresh build chunk hash rotations
  useEffect(() => {
    if (typeof window === 'undefined') return

    const handleChunkError = (event: ErrorEvent | PromiseRejectionEvent) => {
      const error = 'reason' in event ? event.reason : event.error
      const isChunkError =
        error?.name === 'ChunkLoadError' ||
        (error?.message && typeof error.message === 'string' && error.message.includes('Loading chunk')) ||
        (error?.message && typeof error.message === 'string' && error.message.includes('ERR_ABORTED'))

      if (isChunkError) {
        console.warn('Chunk mismatch detected following build update. Auto-refreshing...')
        window.location.reload()
      }
    }

    window.addEventListener('error', handleChunkError)
    window.addEventListener('unhandledrejection', handleChunkError)

    return () => {
      window.removeEventListener('error', handleChunkError)
      window.removeEventListener('unhandledrejection', handleChunkError)
    }
  }, [])

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}
