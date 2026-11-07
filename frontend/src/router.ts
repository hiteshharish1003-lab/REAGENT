import { useSyncExternalStore } from 'react'

export type Route = 'home' | 'archive' | 'inquiry'

const parse = (): Route => {
  const h = window.location.hash.replace(/^#\/?/, '')
  return h === 'archive' || h === 'inquiry' ? h : 'home'
}
const subscribe = (cb: () => void) => {
  window.addEventListener('hashchange', cb)
  return () => window.removeEventListener('hashchange', cb)
}

export const useRoute = (): Route => useSyncExternalStore(subscribe, parse, () => 'home' as Route)

export const hrefFor = (r: Route) => (r === 'home' ? '#/' : `#/${r}`)
