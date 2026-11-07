import { AnimatePresence, motion, useInView } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'

type V = 'supported' | 'contradicted' | 'unsupported'

interface Row {
  text: string
  verdict: V
  fixed?: string // replacement shown after correction; undefined + unsupported = removed
  evidence: string
}

const ROWS: Row[] = [
  { text: 'Adoption grew 18% in 2024, reaching 4.2 million units.', verdict: 'supported', evidence: 'Annual Sector Outlook: "Adoption in the sector grew 18% in 2024, reaching 4.2 million units."' },
  { text: 'Adoption grew 12% in 2024, according to government reporting.', verdict: 'contradicted', fixed: 'Adoption grew 18% in 2024, according to government reporting.', evidence: 'The government outlook states 18%. The 12% figure comes from a university study counting only commercial registrations.' },
  { text: 'Government incentives accounted for roughly a third of new demand.', verdict: 'supported', evidence: 'Annual Sector Outlook: "Government incentives accounted for roughly a third of new demand."' },
  { text: 'The sector will fully replace conventional alternatives by 2026.', verdict: 'unsupported', evidence: 'No cited source makes this claim. The nearest passage is an opinion piece predicting that the market "will double".' },
]

const LABEL: Record<V, string> = { supported: 'Supported', contradicted: 'Contradicted', unsupported: 'Unsupported' }

/** A looping demonstration of the product's core idea: judge each sentence, then correct or remove what fails. */
export default function HeroPreview() {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { amount: 0.3 })
  // 0 = idle; 1..N = N sentences judged; N+1 = corrected
  const [step, setStep] = useState(0)
  const N = ROWS.length

  useEffect(() => {
    if (!inView) return
    const delay = step === 0 ? 1100 : step <= N ? 1250 : 4200
    const t = setTimeout(() => setStep((s) => (s > N ? 0 : s + 1)), delay)
    return () => clearTimeout(t)
  }, [step, inView, N])

  const corrected = step > N
  const judged = Math.min(step, N)
  const judgedRows = ROWS.slice(0, judged)
  const supported = judgedRows.filter((r) => r.verdict === 'supported').length
  const pct = corrected ? 100 : judged ? Math.round((supported / judged) * 100) : 0
  const latest = judged ? ROWS[judged - 1] : null

  return (
    <div className="preview" ref={ref}>
      <div className="preview-bar">
        <span className="label">Verification pass</span>
        <span className="label" style={{ color: 'var(--faint)' }}>Sample report</span>
      </div>
      <div className="preview-body">
        <h4>Sector adoption, 2024</h4>
        <p>
          {ROWS.map((r, i) => {
            const isJudged = i < judged
            const isFixed = corrected && r.verdict !== 'supported'
            const cls = !isJudged ? '' : isFixed ? (r.fixed ? 'rewritten' : 'removed') : `v-${r.verdict}`
            const shown = corrected && r.fixed ? r.fixed : r.text
            return (
              <span key={i} className={`sent ${cls}`}>
                <motion.span className="sent-text" layout="position" animate={{ opacity: corrected && !r.fixed && r.verdict === 'unsupported' ? 0.4 : 1 }}>
                  {shown}
                </motion.span>{' '}
              </span>
            )
          })}
        </p>
      </div>
      <div className="evidence-line" style={{ borderLeftColor: latest && !corrected ? `var(--${latest.verdict === 'supported' ? 'ok' : latest.verdict === 'contradicted' ? 'bad' : 'warn'})` : undefined }}>
        <AnimatePresence mode="wait">
          <motion.div key={corrected ? 'c' : judged} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.25 }}>
            {corrected ? (
              <><b style={{ color: 'var(--accent)' }}>Corrected</b>One figure fixed from its source, one unsupported claim removed.</>
            ) : latest ? (
              <><b style={{ color: `var(--${latest.verdict === 'supported' ? 'ok' : latest.verdict === 'contradicted' ? 'bad' : 'warn'})` }}>{LABEL[latest.verdict]}</b>{latest.evidence}</>
            ) : (
              <><b>Waiting</b>Each sentence is checked against the passages it cites.</>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
      <div className="preview-foot">
        <div className="meter"><motion.i animate={{ scaleX: pct / 100, background: pct >= 85 ? 'var(--ok)' : pct >= 60 ? 'var(--warn)' : 'var(--bad)' }} initial={{ scaleX: 0 }} transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }} /></div>
        <div className="score">Faithfulness <b>{judged || corrected ? `${pct}%` : '--'}</b></div>
      </div>
    </div>
  )
}
