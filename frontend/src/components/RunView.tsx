import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { api } from '../api'
import { useRun } from '../useRun'
import type { Mode } from '../types'
import Pipeline from './Pipeline'
import PlanCard from './PlanCard'
import ReportView from './ReportView'
import SourceDrawer from './SourceDrawer'
import StatsPanel from './StatsRing'
import { Conflicts, Findings, SourceList } from './Insights'

interface Props {
  runId: string
  topic: string
  mode: Mode
  demo: boolean
  onFinished: () => void
}

export default function RunView({ runId, topic, mode, demo, onFinished }: Props) {
  const state = useRun(runId, mode)
  const [open, setOpen] = useState<{ id: number; passage: string } | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const source = open ? state.sources.find((s) => s.id === open.id) ?? null : null
  const finished = state.status === 'done' || state.status === 'error'

  // Refresh sidebar history once a run ends.
  useEffect(() => {
    if (finished) onFinished()
  }, [finished, onFinished])

  const approve = async (q: string[]) => {
    try { setErr(null); await api.approve(runId, q) } catch (e) { setErr((e as Error).message) }
  }

  return (
    <div className="run">
      <div className="run-head">
        <div>
          <div className="label">{mode === 'multi' ? 'Multi-agent inquiry' : 'Single-agent baseline'}{demo && ' · demo data'}</div>
          <h2 className="run-topic">{topic}</h2>
        </div>
        {state.usage && (
          <div className="usage">
            <span>{state.usage.seconds}s</span>
            <span>{state.usage.searches} searches</span>
            <span>{state.usage.calls} model calls</span>
          </div>
        )}
      </div>

      <Pipeline mode={mode} state={state} />

      {state.status === 'error' && (
        <div className="alert">{state.error}</div>
      )}
      {err && <div className="alert">{err}</div>}
      {state.notes.map((n, i) => <div key={i} className="note">{n}</div>)}

      <div className="run-grid">
        <div className="col-main">
          {state.status === 'awaiting_approval' && <PlanCard key={state.plan.join('|')} questions={state.plan} onApprove={approve} />}

          {state.report ? (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
              <ReportView
                report={state.report}
                sources={state.sources}
                verifying={state.stages.verify === 'running'}
                onOpenSource={(id, passage) => setOpen({ id, passage: passage ?? '' })}
              />
            </motion.div>
          ) : (
            state.status !== 'awaiting_approval' && state.status !== 'error' && (
              <div className="card skeleton-card">
                <div className="sk sk-title" />
                {[0, 1, 2, 3].map((i) => <div key={i} className="sk sk-line" style={{ width: `${92 - i * 11}%` }} />)}
                <div className="muted small">{state.sources.length ? 'Analysing and drafting' : 'Finding sources'}</div>
              </div>
            )
          )}
        </div>

        <div className="col-side">
          <StatsPanel before={state.before} after={state.after} />
          <Conflicts conflicts={state.conflicts} sources={state.sources} onOpenSource={(id) => setOpen({ id, passage: '' })} />
          <SourceList sources={state.sources} onOpenSource={(id) => setOpen({ id, passage: '' })} />
          {mode === 'multi' && <Findings findings={state.findings} />}
        </div>
      </div>

      <SourceDrawer source={source} passage={open?.passage ?? ''} onClose={() => setOpen(null)} />
    </div>
  )
}
