import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

export function formatNumber(num: number): string {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M'
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K'
  }
  return num.toString()
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount)
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  if (ms < 3600000) return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`
  return `${Math.floor(ms / 3600000)}h ${Math.floor((ms % 3600000) / 60000)}m`
}

export function formatRelativeTime(date: Date | string | null | undefined): string {
  if (!date) return 'just now'
  const now = new Date()
  let then: Date
  if (typeof date === 'string') {
    let str = date.trim()
    if (!str.endsWith('Z') && !str.includes('+') && !/[-+]\d{2}:\d{2}$/.test(str)) {
      if (str.includes(' ') && !str.includes('T')) {
        str = str.replace(' ', 'T')
      }
      str += 'Z'
    }
    then = new Date(str)
  } else {
    then = new Date(date)
  }

  if (isNaN(then.getTime())) return 'just now'

  const diff = Math.max(0, now.getTime() - then.getTime())

  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (seconds < 60) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days < 7) return `${days}d ago`
  return then.toLocaleDateString()
}

export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout)
    timeout = setTimeout(() => func(...args), wait)
  }
}

export function throttle<T extends (...args: any[]) => any>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle = false
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args)
      inThrottle = true
      setTimeout(() => (inThrottle = false), limit)
    }
  }
}

export function generateId(): string {
  return Math.random().toString(36).substring(2, 9)
}

/**
 * Universal error message formatter.
 * Guarantees a safe string output for any error type (FastAPI validation arrays,
 * error objects, Error instances, strings, nulls) so React never encounters
 * Minified React Error #310 ("Objects are not valid as a React child").
 */
export function formatErrorMessage(err: unknown, fallback = 'An unexpected error occurred'): string {
  if (!err) return fallback
  if (typeof err === 'string') return err.trim().length > 0 ? err : fallback
  if (err instanceof Error) {
    if (typeof err.message === 'string' && err.message.trim().length > 0) {
      return err.message
    }
    return fallback
  }
  if (typeof err === 'object') {
    const record = err as Record<string, unknown>
    // Handle FastAPI detail field: can be string or list of validation dicts
    if (record.detail !== undefined && record.detail !== null) {
      if (typeof record.detail === 'string') return record.detail
      if (Array.isArray(record.detail)) {
        const msgs = record.detail
          .map((item) => (typeof item === 'object' && item && 'msg' in item ? String((item as any).msg) : JSON.stringify(item)))
          .filter(Boolean)
        if (msgs.length > 0) return msgs.join(', ')
      }
      if (typeof record.detail === 'object') {
        try {
          return JSON.stringify(record.detail)
        } catch {
          return fallback
        }
      }
    }
    if (typeof record.message === 'string' && record.message.trim().length > 0) {
      return record.message
    }
    if (typeof record.error === 'string' && record.error.trim().length > 0) {
      return record.error
    }
    if (typeof record.error === 'object' && record.error !== null) {
      return formatErrorMessage(record.error, fallback)
    }
    try {
      return JSON.stringify(err)
    } catch {
      return fallback
    }
  }
  return String(err)
}

