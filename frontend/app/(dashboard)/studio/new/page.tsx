'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function NewDatasetPage() {
  const router = useRouter()

  useEffect(() => {
    // Redirect to studio for now - can be enhanced later
    router.replace('/studio')
  }, [router])

  return null
}