'use client'

import { useEffect, useState } from 'react'
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react'
import { clsx } from 'clsx'
import { playClickSound, playSuccessChime } from '@/lib/audio/sound-effects'

type ToastType = 'success' | 'error' | 'warning' | 'info'

interface Toast {
  id: string
  type: ToastType
  title: string
  description?: string
}

const icons = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}

const styles = {
  success: 'border-[#f26625]/40 bg-[#12121a]/95 text-white shadow-[0_8px_30px_rgba(242,102,37,0.15)]',
  error: 'border-rose-500/40 bg-[#12121a]/95 text-white shadow-[0_8px_30px_rgba(244,63,94,0.15)]',
  warning: 'border-amber-500/40 bg-[#12121a]/95 text-white shadow-[0_8px_30px_rgba(245,158,11,0.15)]',
  info: 'border-cyan-500/40 bg-[#12121a]/95 text-white shadow-[0_8px_30px_rgba(6,182,212,0.15)]',
}

const iconStyles = {
  success: 'text-[#f26625]',
  error: 'text-rose-400',
  warning: 'text-amber-400',
  info: 'text-cyan-400',
}

export function Toaster() {
  const [toasts, setToasts] = useState<Toast[]>([])

  useEffect(() => {
    // Listen for toast events
    const handler = (event: CustomEvent<Toast>) => {
      setToasts((prev) => [...prev, event.detail])
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== event.detail.id))
      }, 5000)
    }

    window.addEventListener('toast' as any, handler)
    return () => window.removeEventListener('toast' as any, handler)
  }, [])

  const removeToast = (id: string) => {
    playClickSound()
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 font-mono">
      {toasts.map((toast) => {
        const Icon = icons[toast.type]
        return (
          <div
            key={toast.id}
            className={clsx(
              'flex items-start gap-3 rounded-lg border p-3.5 shadow-2xl backdrop-blur-md animate-slide-in min-w-[320px] max-w-[420px]',
              styles[toast.type]
            )}
          >
            <Icon className={clsx('h-4.5 w-4.5 shrink-0 mt-0.5', iconStyles[toast.type])} />
            <div className="flex-1 space-y-0.5">
              <p className="text-xs font-bold text-white">{toast.title}</p>
              {toast.description && (
                <p className="text-xs text-[#94a3b8]">{toast.description}</p>
              )}
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="text-[#64748b] hover:text-white p-0.5"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )
      })}
    </div>
  )
}

// Helper function to show toasts
export const toast = {
  show: (type: ToastType, title: string, description?: string) => {
    const id = Math.random().toString(36).substring(7)
    if (type === 'success') {
      playSuccessChime()
    } else {
      playClickSound()
    }
    window.dispatchEvent(
      new CustomEvent('toast', { detail: { id, type, title, description } })
    )
  },
  success: (title: string, description?: string) => toast.show('success', title, description),
  error: (title: string, description?: string) => toast.show('error', title, description),
  warning: (title: string, description?: string) => toast.show('warning', title, description),
  info: (title: string, description?: string) => toast.show('info', title, description),
}
