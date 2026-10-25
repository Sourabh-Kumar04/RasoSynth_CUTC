import { MetadataRoute } from 'next'

export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://rasosynthtune-indiaai.vercel.app'
  const routes = [
    '',
    '/studio',
    '/datasets',
    '/finetune',
    '/orchestration',
    '/review',
    '/quality',
    '/observability',
    '/research',
    '/providers',
    '/settings',
  ]

  const now = new Date()

  return routes.map((route) => ({
    url: `${baseUrl}${route}`,
    lastModified: now,
    changeFrequency: route === '' ? 'daily' : 'hourly',
    priority: route === '' ? 1.0 : 0.8,
  }))
}
