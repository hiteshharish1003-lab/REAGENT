import { useState } from 'react'
import { motion } from 'framer-motion'

interface Props {
  questions: string[]
  onApprove: (q: string[]) => Promise<void>
}

export default function PlanCard({ questions, onApprove }: Props) {
  const [qs, setQs] = useState(questions)
  const [busy, setBusy] = useState(false)
  const valid = qs.filter((q) => q.trim()).length > 0

  const go = async () => {
    setBusy(true)
    try { await onApprove(qs.map((q) => q.trim()).filter(Boolean)) } finally { setBusy(false) }
  }

  return (
    <motion.div className="card plan-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
      <div className="card-title">Research plan <span className="pill pill-amber">Awaiting approval</span></div>
      <p className="muted">Edit, remove or add questions. Searches only start after you approve, which keeps cost under your control.</p>
      <ol className="plan-list">
        {qs.map((q, i) => (
          <motion.li key={i} layout initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}>
            <input value={q} onChange={(e) => setQs(qs.map((x, j) => (j === i ? e.target.value : x)))} />
            <button className="btn btn-quiet btn-danger" onClick={() => setQs(qs.filter((_, j) => j !== i))} aria-label="Remove question">Remove</button>
          </motion.li>
        ))}
      </ol>
      <div className="plan-actions">
        <button className="btn btn-quiet" disabled={qs.length >= 6} onClick={() => setQs([...qs, ''])}>Add question</button>
        <button className="btn btn-solid" disabled={!valid || busy} onClick={go}>Approve and begin</button>
      </div>
    </motion.div>
  )
}
