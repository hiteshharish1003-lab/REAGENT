import { AnimatePresence, motion } from 'framer-motion'
import { useState, type DragEvent } from 'react'
import type { DocInfo, QaSummary } from '../types'

export interface UploadRow { key: string; name: string; progress: number; error?: string; note?: string }

interface Props {
  docs: DocInfo[]
  off: Set<number>
  uploads: UploadRow[]
  history: QaSummary[]
  activeQa: number | null
  onPick: () => void
  onFiles: (files: File[]) => void
  onToggle: (id: number) => void
  onRemoveDoc: (id: number) => void
  onOpenQa: (id: number) => void
  onDeleteQa: (id: number) => void
}

function ago(ts: number) {
  const m = Math.round((Date.now() / 1000 - ts) / 60)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  return h < 24 ? `${h}h ago` : `${Math.round(h / 24)}d ago`
}

export default function Library({ docs, off, uploads, history, activeQa, onPick, onFiles, onToggle, onRemoveDoc, onOpenQa, onDeleteQa }: Props) {
  const [over, setOver] = useState(false)
  const [confirm, setConfirm] = useState<number | null>(null)

  const drop = (e: DragEvent) => {
    e.preventDefault(); setOver(false)
    onFiles(Array.from(e.dataTransfer.files))
  }

  return (
    <aside className="rail">
      <div>
        <div className="rail-head"><span className="label">Library</span><span className="count">{docs.length} {docs.length === 1 ? 'document' : 'documents'}</span></div>
        <div
          className={`dropzone ${over ? 'over' : ''}`}
          role="button"
          tabIndex={0}
          onClick={onPick}
          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onPick())}
          onDragOver={(e) => { e.preventDefault(); setOver(true) }}
          onDragLeave={() => setOver(false)}
          onDrop={drop}
        >
          <b>{over ? 'Release to add' : 'Add documents'}</b>
          <span>PDF, TXT, MD, CSV or JSON, up to 20 MB each</span>
        </div>
      </div>

      <div className="doc-list">
        <AnimatePresence initial={false}>
          {uploads.map((u) => (
            <motion.div key={u.key} layout initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0 }} className={`upload-row ${u.error ? 'err' : ''}`}>
              <div className="stagename">
                <span>{u.name}</span>
                <span>{u.error ? 'Failed' : u.note ? 'Skipped' : u.progress < 1 ? `Uploading ${Math.round(u.progress * 100)}%` : 'Indexing'}</span>
              </div>
              {u.error || u.note ? (
                <div className="small" style={{ marginTop: 6, color: u.error ? undefined : 'var(--muted)' }}>{u.error ?? u.note}</div>
              ) : (
                <div className={`bar ${u.progress >= 1 ? 'indef' : ''}`}>
                  <motion.i initial={false} animate={{ scaleX: u.progress >= 1 ? 1 : u.progress }} transition={{ duration: 0.2 }} style={u.progress >= 1 ? { transform: 'none' } : undefined} />
                </div>
              )}
            </motion.div>
          ))}
          {docs.map((d) => (
            <motion.div key={d.id} layout initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: -12 }} className={`doc ${off.has(d.id) ? 'off' : ''}`}>
              <input type="checkbox" className="check" checked={!off.has(d.id)} onChange={() => onToggle(d.id)} aria-label={`Include ${d.name} in searches`} />
              <div>
                <div className="doc-name">{d.name}</div>
                <div className="doc-meta">{d.pages} {d.pages === 1 ? 'page' : 'pages'} · {d.chunks} passages</div>
              </div>
              {confirm === d.id ? (
                <button className="btn btn-quiet btn-danger" style={{ color: 'var(--bad)' }} onClick={() => { onRemoveDoc(d.id); setConfirm(null) }} onBlur={() => setConfirm(null)} autoFocus>Confirm</button>
              ) : (
                <button className="btn btn-quiet btn-danger" onClick={() => setConfirm(d.id)}>Remove</button>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
        {docs.length === 0 && uploads.length === 0 && <div className="empty-hint">No documents yet. Everything you add stays on this machine.</div>}
      </div>

      <div>
        <div className="rail-head"><span className="label">Previous questions</span><span className="count">{history.length}</span></div>
        <div className="history">
          {history.map((h) => (
            <div key={h.id} style={{ position: 'relative' }}>
              <button className={`history-item ${h.id === activeQa ? 'active' : ''}`} onClick={() => onOpenQa(h.id)}>
                <div className="history-topic">{h.question}</div>
                <div className="history-meta">{ago(h.created_at)}</div>
              </button>
              <button className="btn btn-quiet btn-danger history-del" onClick={() => onDeleteQa(h.id)} aria-label="Delete question">Delete</button>
            </div>
          ))}
          {history.length === 0 && <div className="empty-hint">Answers you generate are saved here.</div>}
        </div>
      </div>
    </aside>
  )
}
