import { motion } from 'framer-motion'
import type { Conflict, Finding, Source } from '../types'

interface Props {
  sources: Source[]
  findings: Finding[]
  conflicts: Conflict[]
  onOpenSource: (id: number) => void
}

export function SourceList({ sources, onOpenSource }: { sources: Source[]; onOpenSource: (id: number) => void }) {
  return (
    <div className="card">
      <div className="card-title">Sources <span className="count">{sources.length}</span></div>
      <div className="source-list">
        {sources.map((s, i) => (
          <motion.button key={s.id} className="source" onClick={() => onOpenSource(s.id)} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i * 0.04, 0.4) }}>
            <span className="source-n">{s.id}</span>
            <span className="source-main">
              <b>{s.title}</b>
              <small>{s.domain}</small>
            </span>
            <span className="trust" title={s.quality_reason}><i style={{ width: `${s.quality * 100}%` }} /></span>
          </motion.button>
        ))}
        {sources.length === 0 && <div className="empty-hint">Waiting for sources…</div>}
      </div>
    </div>
  )
}

export function Conflicts({ conflicts, sources, onOpenSource }: { conflicts: Conflict[]; sources: Source[]; onOpenSource: (id: number) => void }) {
  if (!conflicts.length) return null
  const dom = (id: number) => sources.find((s) => s.id === id)?.domain ?? `source ${id}`
  return (
    <div className="card conflict-card">
      <div className="card-title">Sources disagree <span className="count">{conflicts.length}</span></div>
      {conflicts.map((c, i) => (
        <motion.div key={i} className="conflict" initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}>
          <div className="conflict-topic">{c.topic}</div>
          <div className="conflict-vs">
            {c.claims.map((cl, j) => (
              <button key={j} onClick={() => onOpenSource(cl.source_id)}>
                <span>{cl.claim}</span>
                <small>{dom(cl.source_id)}</small>
              </button>
            ))}
          </div>
          <p className="muted small">{c.explanation}</p>
        </motion.div>
      ))}
    </div>
  )
}

export function Findings({ findings }: Pick<Props, 'findings'>) {
  if (!findings.length) return null
  return (
    <div className="card">
      <div className="card-title">Key findings <span className="count">{findings.length}</span></div>
      <ul className="findings">
        {findings.map((f, i) => (
          <motion.li key={i} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }}>{f.text}</motion.li>
        ))}
      </ul>
    </div>
  )
}
