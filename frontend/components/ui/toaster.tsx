'use client'

import { useEffect, useState } from 'react'
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react'
import { clsx } from 'clsx'

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
  success: 'border-success/30 bg-success/10',
  error: 'border-error/30 bg-error/10',
  warning: 'border-warning/30 bg-warning/10',
  info: 'border-info/30 bg-info/10',
}

const iconStyles = {
  success: 'text-success',
  error: 'text-error',
  warning: 'text-warning',
  info: 'text-info',
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
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => {
        const Icon = icons[toast.type]
        return (
          <div
            key={toast.id}
            className={clsx(
              'flex items-start gap-3 rounded-lg border p-4 shadow-lg backdrop-blur-sm animate-slide-in min-w-[320px] max-w-[420px]',
              styles[toast.type]
            )}
          >
            <Icon className={clsx('h-5 w-5 shrink-0 mt-0.5', iconStyles[toast.type])} />
            <div className="flex-1 space-y-1">
              <p className="text-sm font-medium">{toast.title}</p>
              {toast.description && (
                <p className="text-xs text-muted-foreground">{toast.description}</p>
              )}
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
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
    window.dispatchEvent(
      new CustomEvent('toast', { detail: { id, type, title, description } })
    )
  },
  success: (title: string, description?: string) => toast.show('success', title, description),
  error: (title: string, description?: string) => toast.show('error', title, description),
  warning: (title: string, description?: string) => toast.show('warning', title, description),
  info: (title: string, description?: string) => toast.show('info', title, description),
}
