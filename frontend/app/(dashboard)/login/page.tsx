'use client'

import React, { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { LogIn, KeyRound, User, AlertCircle, ArrowLeft, ShieldCheck } from 'lucide-react'
import { api } from '@/lib/api/client'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/ui/page-header'

export default function LoginPage() {
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username || !password) {
      setError('Please enter both username and password.')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const res = await api.login(username, password)
      if (res && res.token) {
        setSuccess(true)
        setTimeout(() => {
          router.push('/dashboard')
        }, 600)
      } else {
        setError(res?.message || 'Login failed: No access token received.')
      }
    } catch (err: any) {
      setError(err?.message || 'Authentication failed. Please verify credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-md mx-auto py-12 px-4 space-y-6">
      <Link
        href="/dashboard"
        className="inline-flex items-center text-xs font-mono text-[#a8a29e] hover:text-white transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
        Back to Dashboard
      </Link>

      <PageHeader
        eyebrow="Authentication"
        title="Sign In"
        purpose="Enter your RasoSynthTune credentials to access datasets, training jobs, and system administration."
      />

      <div className="rounded-md border border-[#272738] bg-[#12121a] p-6 shadow-xl">
        <form onSubmit={handleLogin} className="space-y-4">
          {error && (
            <div className="flex items-start gap-2.5 p-3 rounded-md bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="flex items-start gap-2.5 p-3 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-mono">
              <ShieldCheck className="w-4 h-4 shrink-0 text-emerald-400 mt-0.5" />
              <span>Authenticated successfully. Redirecting…</span>
            </div>
          )}

          <div className="space-y-1.5">
            <label className="block text-xs font-mono text-[#a8a29e] uppercase">
              Username
            </label>
            <div className="relative">
              <User className="absolute left-3 top-2.5 h-4 w-4 text-[#a8a29e]" />
              <input
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin or username"
                className="w-full rounded-md border border-[#272738] bg-[#161622] pl-9 pr-3 py-2 text-xs font-mono text-white placeholder-zinc-500 focus:outline-none focus:border-[#f26625]"
                disabled={loading}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="block text-xs font-mono text-[#a8a29e] uppercase">
              Password
            </label>
            <div className="relative">
              <KeyRound className="absolute left-3 top-2.5 h-4 w-4 text-[#a8a29e]" />
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full rounded-md border border-[#272738] bg-[#161622] pl-9 pr-3 py-2 text-xs font-mono text-white placeholder-zinc-500 focus:outline-none focus:border-[#f26625]"
                disabled={loading}
              />
            </div>
          </div>

          <Button
            type="submit"
            disabled={loading}
            className="w-full mt-2 rounded-md bg-[#f26625] hover:bg-[#de581a] font-mono text-xs font-bold text-white py-2"
          >
            {loading ? (
              'Authenticating…'
            ) : (
              <span className="flex items-center justify-center gap-1.5">
                <LogIn className="w-3.5 h-3.5" /> Sign In
              </span>
            )}
          </Button>
        </form>

        <div className="mt-6 pt-4 border-t border-[#1c1c28] text-xs font-mono text-[#a8a29e] space-y-1">
          <p>Tokens are stored securely in browser localStorage and attached to all API data calls.</p>
          <p className="text-xs text-zinc-500">Unauthenticated calls fail closed with 401.</p>
        </div>
      </div>
    </div>
  )
}
