import { useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import type { Report, Sentence, Source, Verdict } from '../types'

const META: Record<Verdict, { label: string }> = {
  supported: { label: 'Supported' },
  contradicted: { label: 'Contradicted' },
  unsupported: { label: 'Unsupported' },
}

interface Props {
  report: Report
  sources: Source[]
  verifying: boolean
  onOpenSource: (id: number, passage?: string) => void
  hideTitle?: boolean
  bullets?: boolean
}

export default function ReportView({ report, sources, verifying, onOpenSource, hideTitle = false, bullets = false }: Props) {
  const [filter, setFilter] = useState<Verdict | 'all'>('all')
  const [showRemoved, setShowRemoved] = useState(false)
  const [activeId, setActiveId] = useState<string | null>(null)

  const all = useMemo(() => report.sections.flatMap((s) => s.sentences), [report])
  const live = all.filter((s) => s.action !== 'removed')
  const removed = all.filter((s) => s.action === 'removed')
  const counts = useMemo(() => {
    const c = { supported: 0, contradicted: 0, unsupported: 0 }
    live.forEach((s) => s.verdict && c[s.verdict]++)
    return c
  }, [live])
  const active = all.find((s) => s.id === activeId) ?? null
  const srcById = (id: number | null) => sources.find((s) => s.id === id)

  return (
    <div className="card report-card">
      <div className="report-head">
        {!hideTitle && <h2>{report.title}</h2>}
        <div className="filters">
          <button className={filter === 'all' ? 'on' : ''} onClick={() => setFilter('all')}>All {live.length}</button>
          {(Object.keys(META) as Verdict[]).map((v) => (
            <button key={v} className={`${filter === v ? 'on' : ''} f-${v}`} onClick={() => setFilter(filter === v ? 'all' : v)} disabled={!counts[v]}>
              <i className={`sw ${v === 'supported' ? 'ok' : v === 'contradicted' ? 'bad' : 'warn'}`} /> {counts[v]}
            </button>
          ))}
          {removed.length > 0 && (
            <button className="ghost" onClick={() => setShowRemoved(!showRemoved)}>
              {showRemoved ? 'Hide' : 'Show'} {removed.length} removed
            </button>
          )}
        </div>
      </div>

      {verifying && <div className="verifying"><span className="scan" /> Checking every sentence against its source</div>}

      <div className={`report-body ${bullets ? 'bullets' : ''}`}>
        {report.sections.map((sec, si) => (
          <section key={si}>
            <h3>{sec.heading}</h3>
            <p>
              {sec.sentences.map((s) => {
                if (s.action === 'removed' && !showRemoved) return null
                const dim = filter !== 'all' && s.verdict !== filter
                return (
                  <Sent key={s.id} s={s} dim={dim} active={s.id === activeId} onActivate={() => setActiveId(s.id === activeId ? null : s.id)} onCite={(id) => onOpenSource(id, s.evidence_source_id === id ? s.evidence : undefined)} />
                )
              })}
            </p>
          </section>
        ))}
      </div>

      <AnimatePresence>
        {active && active.verdict && (
          <motion.div className={`evidence ev-${active.verdict}`} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 14 }}>
            <div className="ev-head">
              {META[active.verdict].label}
              {active.action === 'rewritten' && <span className="pill pill-accent">Corrected by verifier</span>}
              {active.action === 'removed' && <span className="pill pill-red">Removed from final report</span>}
            </div>
            {active.original && <p className="ev-orig"><span>Original claim</span>{active.original}</p>}
            {active.evidence ? (
              <blockquote onClick={() => active.evidence_source_id && onOpenSource(active.evidence_source_id, active.evidence)}>
                “{active.evidence}”
                <cite>{srcById(active.evidence_source_id)?.domain ?? 'source'}, view in context</cite>
              </blockquote>
            ) : (
              <p className="muted small">No passage in the cited sources states this claim.</p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function Sent({ s, dim, active, onActivate, onCite }: { s: Sentence; dim: boolean; active: boolean; onActivate: () => void; onCite: (id: number) => void }) {
  const v = s.verdict ?? 'pending'
  return (
    <motion.span layout="position" className={`sent v-${v} ${s.action} ${dim ? 'dim' : ''} ${active ? 'active' : ''}`} initial={{ opacity: 0 }} animate={{ opacity: dim ? 0.3 : 1 }}>
      <span className="sent-text" onClick={onActivate} tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && onActivate()}>{s.text}</span>
      {s.source_ids.map((id) => (
        <button key={id} className="cite" onClick={() => onCite(id)} title="Open source">{id}</button>
      ))}{' '}
    </motion.span>
  )
}
