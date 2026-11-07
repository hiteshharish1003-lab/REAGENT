import { animate, motion, useMotionValue, useTransform } from 'framer-motion'
import { useEffect } from 'react'
import type { Stats } from '../types'

function Ring({ value, size = 96 }: { value: number; size?: number }) {
  const r = (size - 12) / 2
  const c = 2 * Math.PI * r
  const mv = useMotionValue(0)
  const dash = useTransform(mv, (v) => `${v * c} ${c}`)
  const label = useTransform(mv, (v) => `${Math.round(v * 100)}`)
  useEffect(() => {
    const ctl = animate(mv, value, { duration: 1.1, ease: 'easeOut' })
    return () => ctl.stop()
  }, [value, mv])
  const tone = value >= 0.85 ? 'var(--ok)' : value >= 0.6 ? 'var(--warn)' : 'var(--bad)'
  return (
    <div className="ring" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} className="ring-bg" />
        <motion.circle cx={size / 2} cy={size / 2} r={r} className="ring-fg" style={{ strokeDasharray: dash, stroke: tone }} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      </svg>
      <div className="ring-label"><motion.b>{label}</motion.b><small>%</small></div>
    </div>
  )
}

export default function StatsPanel({ before, after, settled = false }: { before: Stats | null; after: Stats | null; settled?: boolean }) {
  if (!before) return null
  const final = after ?? before
  return (
    <div className="card stats-card">
      <div className="card-title">Faithfulness</div>
      <div className="stats-row">
        <Ring value={final.faithfulness} />
        <div className="stats-detail">
          {after && (
            <div className="delta">
              <span className="muted">Before correction</span>
              <b>{Math.round(before.faithfulness * 100)}%</b>
              <span className="arrow">→</span>
              <b className="good">{Math.round(after.faithfulness * 100)}%</b>
            </div>
          )}
          <div className="muted small">{after ? 'Found by the verifier' : settled ? 'Claims checked' : 'Claims checked so far'}</div>
          <div className="legend">
            <span><i className="sw ok" />{before.supported} supported</span>
            <span><i className="sw bad" />{before.contradicted} contradicted</span>
            <span><i className="sw warn" />{before.unsupported} unsupported</span>
            {!!before.unchecked && <span><i className="sw" />{before.unchecked} unchecked</span>}
          </div>
          <p className="muted small">Share of claims backed by their cited source, judged sentence by sentence.</p>
        </div>
      </div>
    </div>
  )
}
