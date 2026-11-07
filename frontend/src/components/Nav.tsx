import { motion, useScroll, useSpring } from 'framer-motion'
import { hrefFor, type Route } from '../router'

export type Theme = 'dark' | 'light'

interface Props {
  route: Route
  theme: Theme
  onTheme: (t: Theme) => void
}

const LINKS: { route: Route; label: string; hideSmall?: boolean }[] = [
  { route: 'home', label: 'Overview', hideSmall: true },
  { route: 'archive', label: 'Archive' },
  { route: 'inquiry', label: 'Inquiry' },
]

export default function Nav({ route, theme, onTheme }: Props) {
  const { scrollYProgress } = useScroll()
  const scaleX = useSpring(scrollYProgress, { stiffness: 140, damping: 30, mass: 0.4 })
  return (
    <>
      <motion.div className="progress" style={{ scaleX }} />
      <header className="nav">
        <a className="wordmark" href={hrefFor('home')} aria-label="REAGENT, home">
          REAGENT <small>Evidence engine</small>
        </a>
        <nav className="nav-links" aria-label="Primary">
          {LINKS.map((l) => (
            <a key={l.route} href={hrefFor(l.route)} className={`nav-link ${route === l.route ? 'on' : ''} ${l.hideSmall ? 'hide-sm' : ''}`} aria-current={route === l.route ? 'page' : undefined}>
              {route === l.route && <motion.span layoutId="nav-pill" className="pill-bg" transition={{ type: 'spring', stiffness: 380, damping: 32 }} />}
              {l.label}
            </a>
          ))}
          <div className="theme-switch" role="group" aria-label="Theme">
            {(['dark', 'light'] as Theme[]).map((t) => (
              <button key={t} className={theme === t ? 'on' : ''} onClick={() => onTheme(t)} aria-pressed={theme === t}>
                {theme === t && <motion.span layoutId="theme-thumb" className="thumb" transition={{ type: 'spring', stiffness: 400, damping: 34 }} />}
                {t === 'dark' ? 'Dark' : 'Light'}
              </button>
            ))}
          </div>
        </nav>
      </header>
    </>
  )
}
