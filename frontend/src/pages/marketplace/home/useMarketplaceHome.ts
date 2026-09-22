import { useEffect, useState } from 'react'
import { getMarketplaceHome, type MarketplaceHomeResponse } from '../../../entities/marketplace/api'
import { ApiError } from '../../../shared/api/client'

interface State {
  data: MarketplaceHomeResponse | null
  loading: boolean
  error: string | null
}

/** Один запрос GET /api/marketplace/home. M-F2. */
export function useMarketplaceHome() {
  const [state, setState] = useState<State>({ data: null, loading: true, error: null })

  useEffect(() => {
    let cancelled = false
    setState((s) => ({ ...s, loading: true, error: null }))
    getMarketplaceHome()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null })
      })
      .catch((err) => {
        if (!cancelled) {
          setState({
            data: null,
            loading: false,
            error: err instanceof ApiError ? err.message : 'Не удалось загрузить главную маркетплейса',
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  return state
}
