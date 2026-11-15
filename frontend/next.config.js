const path = require('path')
const { execSync } = require('child_process')

let gitCommit = process.env.VERCEL_GIT_COMMIT_SHA || process.env.NEXT_PUBLIC_GIT_COMMIT_SHA || ''
if (!gitCommit) {
  try {
    gitCommit = execSync('git rev-parse --short HEAD').toString().trim()
  } catch {
    gitCommit = 'dev'
  }
}
const shortCommit = gitCommit ? gitCommit.slice(0, 7) : 'dev'

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  env: {
    NEXT_PUBLIC_GIT_COMMIT_SHA: shortCommit,
    NEXT_PUBLIC_APP_VERSION: '2.0.0',
  },
  images: {
    // P0: the previous wildcard ('**') let Next.js optimise (and thereby
    // proxy) images from ANY https host. No remote images are used anywhere
    // in this frontend today — every image is served locally from public/
    // (mascot layers, favicons) — so the allowlist is intentionally empty.
    // Add a host here only when a real remote-image need appears, with the
    // exact hostname (never '**'), and note why in the commit message.
    remotePatterns: [],
  },
  experimental: {
    serverActions: {
      bodySizeLimit: '10mb',
    },
  },
  async redirects() {
    return [
      {
        source: '/telemetry',
        destination: '/observability',
        permanent: true,
      },
      {
        source: '/models',
        destination: '/finetune',
        permanent: true,
      },
    ]
  },
  webpack: (config) => {
    config.resolve.alias['@'] = path.resolve(__dirname)
    config.resolve.modules = [
      path.resolve(__dirname),
      path.resolve(__dirname, 'node_modules'),
      'node_modules',
    ]
    return config
  },
}

module.exports = nextConfig
