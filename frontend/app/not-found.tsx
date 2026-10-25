import Link from 'next/link'
import { BrandLogo } from '@/components/ui/brand-logo'
import { Home, ArrowRight, Database, FlaskConical } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function NotFound() {
  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white flex flex-col items-center justify-center p-6 font-mono text-center">
      <BrandLogo size={48} className="mb-6" />
      <span className="px-2.5 py-0.5 rounded bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs uppercase tracking-wider mb-2">
        HTTP 404 · Route Not Found
      </span>
      <h1 className="text-2xl font-bold text-white mb-2">Endpoint or Resource Does Not Exist</h1>
      <p className="text-xs text-[#94a3b8] max-w-md mb-8">
        The requested studio route, dataset artifact, or model checkpoint could not be found on this deployment.
      </p>

      <div className="flex flex-wrap items-center justify-center gap-3">
        <Link href="/">
          <Button
            className="bg-[#f26625] hover:bg-[#de581a] text-white text-xs font-bold font-mono h-9 px-4 rounded-md flex items-center gap-2"
          >
            <Home className="w-3.5 h-3.5" />
            Home Overview
          </Button>
        </Link>
        <Link href="/studio">
          <Button
            variant="outline"
            className="border-[#272738] bg-[#12121a] hover:bg-[#161622] text-white text-xs font-mono h-9 px-4 rounded-md flex items-center gap-2"
          >
            <FlaskConical className="w-3.5 h-3.5 text-[#f26625]" />
            Dataset Studio
          </Button>
        </Link>
        <Link href="/datasets">
          <Button
            variant="outline"
            className="border-[#272738] bg-[#12121a] hover:bg-[#161622] text-white text-xs font-mono h-9 px-4 rounded-md flex items-center gap-2"
          >
            <Database className="w-3.5 h-3.5 text-cyan-400" />
            Data Library
          </Button>
        </Link>
      </div>
    </div>
  )
}
