import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { api } from './api'
import Backdrop from './components/Backdrop'
import Nav, { type Theme } from './components/Nav'
import Archive from './pages/Archive'
import Inquiry from './pages/Inquiry'
import Landing from './pages/Landing'
import { useRoute } from './router'

export default function App() {
  const route = useRoute()
  const [demo, setDemo] = useState(false)
  const [offline, setOffline] = useState<string | null>(null)
  const [theme, setTheme] = useState<Theme>(() => {
    try { return (localStorage.getItem('theme') as Theme) || 'dark' } catch { return 'dark' }
  })

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#08080a' : '#f6f5f1')
    try { localStorage.setItem('theme', theme) } catch { /* storage unavailable */ }
  }, [theme])

  useEffect(() => {
    api.health()
      .then((h) => setDemo(h.mock_llm || h.mock_search))
      .catch(() => setOffline('Cannot reach the backend on port 8000. Start it with: uvicorn app.main:app'))
  }, [])

  useEffect(() => { window.scrollTo({ top: 0, behavior: 'instant' }) }, [route])

  const open = (r: 'archive' | 'inquiry') => { window.location.hash = `/${r}` }

  return (
    <div className="shell">
      <Backdrop calm={route !== 'home'} />
      <Nav route={route} theme={theme} onTheme={setTheme} />
      <AnimatePresence mode="wait" initial={false}>
        <motion.div key={route} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}>
          {route === 'home' && <Landing onOpen={open} />}
          {route === 'archive' && <Archive demo={demo} offline={offline} />}
          {route === 'inquiry' && <Inquiry demo={demo} offline={offline} />}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
