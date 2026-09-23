import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useFeature } from '../shared/lib/useFeature'

export function RequireFeature({ feature, children }: { feature: 'storefront'; children: ReactNode }) {
  const enabled = useFeature(feature)
  if (!enabled) {
    return <Navigate to="/" replace />
  }
  return children
}
