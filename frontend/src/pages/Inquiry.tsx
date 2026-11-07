import { AnimatePresence, motion } from 'framer-motion'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import ResearchComposer from '../components/ResearchComposer'
import RunView from '../components/RunView'
import type { Mode, RunSummary } from '../types'

interface Active { id: string; topic: string; mode: Mode }

function ago(ts: number) {
  const m = Math.round((Date.now() / 1000 - ts) / 60)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  return h < 24 ? `${h}h ago` : `${Math.round(h / 24)}d ago`
}

export default function Inquiry({ demo, offline }: { demo: boolean; offline: string | null }) {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [active, setActive] = useState<Active | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(() => { api.listRuns().then(setRuns).catch(() => {}) }, [])
  useEffect(() => { refresh() }, [refresh])

  const start = async (topic: string, mode: Mode, approval: boolean) => {
    setBusy(true); setError(null)
    try {
      const { id } = await api.createRun(topic, mode, approval)
      setActive({ id, topic, mode })
      refresh()
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  const remove = async (id: string) => {
    await api.deleteRun(id)
    if (active?.id === id) setActive(null)
    refresh()
  }

  return (
    <div className="page">
      <div className="workspace">
        <aside className="rail">
          <button className="btn btn-solid" onClick={() => setActive(null)}>New inquiry</button>
          <div>
            <div className="rail-head"><span className="label">History</span><span className="count">{runs.length}</span></div>
            <div className="history">
              <AnimatePresence initial={false}>
                {runs.map((r) => (
                  <motion.div key={r.id} layout initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, height: 0 }} style={{ position: 'relative' }}>
                    <button className={`history-item ${r.id === active?.id ? 'active' : ''}`} onClick={() => setActive({ id: r.id, topic: r.topic, mode: r.mode })}>
                      <div className="history-topic">{r.topic}</div>
                      <div className="history-meta">
                        <span className={`dot dot-${r.status}`} />
                        {r.mode === 'multi' ? 'Multi' : 'Single'} · {ago(r.created_at)}
                        {r.stats && r.stats.total > 0 && <span className="history-score">{Math.round(r.stats.faithfulness * 100)}%</span>}
                      </div>
                    </button>
                    <button className="btn btn-quiet btn-danger history-del" onClick={() => remove(r.id)} aria-label={`Delete ${r.topic}`}>Delete</button>
                  </motion.div>
                ))}
              </AnimatePresence>
              {runs.length === 0 && <div className="empty-hint">Your inquiries will appear here.</div>}
            </div>
          </div>
        </aside>
        <main className="stage">
          <div className="stage-inner">
            {(offline || error) && <div className="alert" style={{ marginTop: 0, marginBottom: 20 }}>{offline ?? error}</div>}
            {active ? (
              <RunView key={active.id} runId={active.id} topic={active.topic} mode={active.mode} demo={demo} onFinished={refresh} />
            ) : (
              <ResearchComposer busy={busy} demo={demo} onSubmit={start} />
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
