import { motion, useInView } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'

/** Ticks only while on screen, so off-screen demos cost nothing. */
function useTicker(ms: number, max: number) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { amount: 0.2 })
  const [t, setT] = useState(0)
  useEffect(() => {
    if (!inView) return
    const id = setInterval(() => setT((v) => (v + 1 > max ? 0 : v + 1)), ms)
    return () => clearInterval(id)
  }, [inView, ms, max])
  return { ref, t }
}

const QUESTION = 'What did the audit find about retention?'
const PASSAGES = [
  { where: 'Audit 2025 · p. 14', text: 'Records are retained for seven years unless…', rel: 1 },
  { where: 'Policy handbook · p. 3', text: 'Retention schedules are reviewed annually by…', rel: 0.72 },
  { where: 'Audit 2025 · p. 21', text: 'Two departments exceeded the stated period…', rel: 0.48 },
]

export function ArchiveDemo() {
  const { ref, t } = useTicker(85, QUESTION.length + 70)
  const typed = Math.max(0, Math.min(QUESTION.length, t - 8))
  const shown = t < QUESTION.length + 18 ? 0 : t < QUESTION.length + 28 ? 1 : t < QUESTION.length + 38 ? 2 : 3
  return (
    <div className="engine-demo" ref={ref} aria-hidden>
      <div className="demo-files"><span>audit-2025.pdf</span><span>policy-handbook.pdf</span><span>notes.md</span></div>
      <div className="demo-q">{QUESTION.slice(0, typed)}<span className="caret" /></div>
      {PASSAGES.map((p, i) => (
        <motion.div key={p.where} className="demo-pass" initial={false} animate={{ opacity: i < shown ? 1 : 0, y: i < shown ? 0 : 8 }} transition={{ duration: 0.4 }}>
          <b>{p.where}</b>
          <span>{p.text}</span>
          <span className="bar"><motion.i initial={false} animate={{ scaleX: i < shown ? p.rel : 0 }} transition={{ duration: 0.6, delay: 0.1 }} /></span>
        </motion.div>
      ))}
    </div>
  )
}

const STEPS: [string, string][] = [
  ['Plan', '4 questions'],
  ['Research', '9 sources'],
  ['Analyse', '2 conflicts'],
  ['Write', '14 sentences'],
  ['Verify', '12 supported'],
  ['Correct', '2 revised'],
]

export function InquiryDemo() {
  const { ref, t } = useTicker(1000, STEPS.length + 2)
  return (
    <div className="engine-demo" ref={ref} aria-hidden>
      <div className="demo-steps">
        {STEPS.map(([name, detail], i) => {
          const state = t > i + 1 ? 'done' : t === i + 1 ? 'on' : ''
          return (
            <div key={name} className={`demo-step ${state}`}>
              <i />
              {name}
              <motion.small initial={false} animate={{ opacity: state ? 1 : 0 }}>{detail}</motion.small>
            </div>
          )
        })}
      </div>
    </div>
  )
}
