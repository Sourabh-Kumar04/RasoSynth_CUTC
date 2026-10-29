const path = require('path')

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
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
  async rewrites() {
    return [
      {
        source: '/jobs/:path*',
        destination: '/api/proxy/jobs/:path*',
      },
      {
        source: '/datasets/:path*',
        destination: '/api/proxy/datasets/:path*',
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
