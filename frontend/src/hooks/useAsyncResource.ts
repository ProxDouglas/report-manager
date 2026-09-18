import { useCallback, useEffect, useState } from 'react'

type CacheEntry<T> = {
  value: T
  cachedAt: number
}

const cache = new Map<string, CacheEntry<unknown>>()
const cacheTtlMs = 30_000

export function invalidateResource(key: string): void {
  cache.delete(key)
}

export function useAsyncResource<T>(key: string, loader: (signal: AbortSignal) => Promise<T>, enabled = true) {
  const cached = cache.get(key) as CacheEntry<T> | undefined
  const [data, setData] = useState<T | undefined>(cached?.value)
  const [error, setError] = useState<Error | null>(null)
  const [loading, setLoading] = useState(enabled && !cached)

  const refresh = useCallback(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    loader(controller.signal)
      .then((value) => {
        cache.set(key, { value, cachedAt: Date.now() })
        setData(value)
      })
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === 'AbortError') {
          return
        }
        if (requestError instanceof Error) {
          setError(requestError)
          return
        }
        setError(new Error('Não foi possível carregar o recurso.'))
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [key, loader])

  useEffect(() => {
    if (!enabled) {
      return
    }
    if (cached && Date.now() - cached.cachedAt < cacheTtlMs) {
      return
    }
    return refresh()
  }, [cached, enabled, refresh])

  return { data, error, loading, refresh }
}
