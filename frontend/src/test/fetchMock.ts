import { vi } from 'vitest'

export type FetchRoute = (url: string, init?: RequestInit) => Response | Promise<Response>

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export function installFetchMock(route: FetchRoute) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
    const url = typeof input === 'string' ? input : input instanceof Request ? input.url : input.toString()
    return Promise.resolve(route(url, init))
  })
}
