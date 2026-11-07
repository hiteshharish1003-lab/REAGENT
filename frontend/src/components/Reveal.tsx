import { animate, motion, useInView, useMotionValue, useTransform } from 'framer-motion'
import { Fragment, useEffect, useRef, type ReactNode } from 'react'

export function Reveal({ children, delay = 0, y = 26, className }: { children: ReactNode; delay?: number; y?: number; className?: string }) {
  return (
    <motion.div className={className} initial={{ opacity: 0, y }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '0px 0px -12% 0px' }} transition={{ duration: 0.8, delay, ease: [0.22, 1, 0.36, 1] }}>
      {children}
    </motion.div>
  )
}

export function CountUp({ to }: { to: number }) {
  const ref = useRef<HTMLElement>(null)
  const inView = useInView(ref, { once: true })
  const mv = useMotionValue(0)
  const text = useTransform(mv, (v) => String(Math.round(v)))
  useEffect(() => {
    if (!inView) return
    const c = animate(mv, to, { duration: 1.4, ease: [0.22, 1, 0.36, 1] })
    return () => c.stop()
  }, [inView, mv, to])
  return <motion.b ref={ref}>{text}</motion.b>
}

/** Headline that rises word by word. Words wrapped in [[ ]] render emphasised. */
export function RiseWords({ text, delay = 0.1 }: { text: string; delay?: number }) {
  const tokens = text.split(' ').map((raw, i, all) => {
    const opens = all.slice(0, i + 1).filter((w) => w.startsWith('[[')).length
    const closed = all.slice(0, i).filter((w) => w.endsWith(']]')).length
    return { word: raw.replace('[[', '').replace(']]', ''), em: opens > closed }
  })
  return (
    <>
      {tokens.map((t, i) => (
        <Fragment key={i}>
          <span className="word">
            <motion.span initial={{ y: '115%' }} animate={{ y: 0 }} transition={{ duration: 0.9, delay: delay + i * 0.07, ease: [0.22, 1, 0.36, 1] }}>
              {t.em ? <em>{t.word}</em> : t.word}
            </motion.span>
          </span>{' '}
        </Fragment>
      ))}
    </>
  )
}
