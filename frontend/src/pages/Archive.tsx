import { AnimatePresence, motion } from 'framer-motion'
import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Library, { type UploadRow } from '../components/Library'
import ReportView from '../components/ReportView'
import SourceDrawer from '../components/SourceDrawer'
import StatsPanel from '../components/StatsRing'
import type { DocAnswer, DocInfo, Passage, QaSummary, Source } from '../types'

type Phase = 'retrieving' | 'answering' | 'done' | 'error'

interface Exchange {
  key: number
  question: string
  phase: Phase
  passages: Passage[]
  answer: DocAnswer | null
  error: string | null
}

const ACCEPT = '.pdf,.txt,.md,.markdown,.csv,.log,.json'

function PassageGrid({ items, onOpen }: { items: { n: number; title: string; text: string; relevance?: number }[]; onOpen: (n: number) => void }) {
  return (
    <div className="passages">
      {items.map((p, i) => (
        <motion.button key={p.n} className="passage" onClick={() => onOpen(p.n)} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.07, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}>
          <div className="passage-top">
            <span>[{p.n}]</span>
            <span>{p.title}</span>
            {p.relevance !== undefined && <span className="rel"><motion.i initial={{ scaleX: 0 }} animate={{ scaleX: p.relevance }} transition={{ delay: 0.25 + i * 0.07, duration: 0.7 }} /></span>}
          </div>
          <p>{p.text}</p>
        </motion.button>
      ))}
    </div>
  )
}

export default function Archive({ demo, offline }: { demo: boolean; offline: string | null }) {
  const [docs, setDocs] = useState<DocInfo[]>([])
  const [off, setOff] = useState<Set<number>>(new Set())
  const [uploads, setUploads] = useState<UploadRow[]>([])
  const [history, setHistory] = useState<QaSummary[]>([])
  const [ex, setEx] = useState<Exchange | null>(null)
  const [question, setQuestion] = useState('')
  const [verify, setVerify] = useState(true)
  const [open, setOpen] = useState<{ id: number; passage: string } | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const seq = useRef(0)

  const refreshDocs = useCallback(() => { api.listDocs().then(setDocs).catch(() => {}) }, [])
  const refreshHistory = useCallback(() => { api.qaHistory().then(setHistory).catch(() => {}) }, [])
  useEffect(() => { refreshDocs(); refreshHistory() }, [refreshDocs, refreshHistory])

  const patchUpload = (key: string, patch: Partial<UploadRow>) => setUploads((u) => u.map((r) => (r.key === key ? { ...r, ...patch } : r)))
  const dropUpload = (key: string, after = 0) => setTimeout(() => setUploads((u) => u.filter((r) => r.key !== key)), after)

  const addFiles = (files: File[]) => {
    files.forEach(async (file) => {
      const key = `${Date.now()}-${seq.current++}-${file.name}`
      setUploads((u) => [{ key, name: file.name, progress: 0 }, ...u])
      try {
        const doc = await api.uploadDoc(file, (f) => patchUpload(key, { progress: f }))
        if (doc.duplicate) { patchUpload(key, { note: 'Already in your library.' }); dropUpload(key, 3500) } else dropUpload(key)
        refreshDocs()
      } catch (e) {
        patchUpload(key, { error: (e as Error).message })
        dropUpload(key, 6000)
      }
    })
  }

  const toggle = (id: number) => setOff((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n })
  const removeDoc = async (id: number) => { await api.deleteDoc(id); setOff((s) => { const n = new Set(s); n.delete(id); return n }); refreshDocs() }

  const active = docs.filter((d) => !off.has(d.id))
  const canAsk = question.trim().length >= 3 && active.length > 0 && ex?.phase !== 'retrieving' && ex?.phase !== 'answering'

  const ask = async () => {
    if (!canAsk) return
    const q = question.trim()
    const key = ++seq.current
    setOpen(null)
    setEx({ key, question: q, phase: 'retrieving', passages: [], answer: null, error: null })
    try {
      const { passages } = await api.retrieve(q, off.size ? active.map((d) => d.id) : [])
      if (!passages.length) {
        setEx({ key, question: q, phase: 'done', passages: [], answer: null, error: null })
        return
      }
      setEx((cur) => (cur && cur.key === key ? { ...cur, phase: 'answering', passages } : cur))
      const answer = await api.answer(q, passages.map((p) => p.id), verify)
      setEx((cur) => (cur && cur.key === key ? { ...cur, phase: 'done', answer } : cur))
      refreshHistory()
    } catch (e) {
      setEx((cur) => (cur && cur.key === key ? { ...cur, phase: 'error', error: (e as Error).message } : cur))
    }
  }

  const openQa = async (id: number) => {
    try {
      const answer = await api.qaItem(id)
      setQuestion(answer.question)
      setOpen(null)
      setEx({ key: ++seq.current, question: answer.question, phase: 'done', passages: [], answer, error: null })
    } catch { refreshHistory() }
  }
  const deleteQa = async (id: number) => { await api.qaDelete(id); if (ex?.answer?.id === id) setEx(null); refreshHistory() }

  const sources: Source[] = ex?.answer?.sources ?? []
  const openSource = open ? sources.find((s) => s.id === open.id) ?? null : null
  const retrievalCards = ex?.answer
    ? ex.answer.sources.map((s, i) => ({ n: s.id, title: s.title, text: s.content, relevance: ex.passages[i]?.relevance }))
    : ex?.passages.map((p, i) => ({ n: i + 1, title: `${p.name}, p. ${p.page}`, text: p.text, relevance: p.relevance })) ?? []
  const phaseOf = (p: 'retrieve' | 'answer') => {
    if (!ex) return ''
    if (p === 'retrieve') return ex.phase === 'retrieving' ? 'on' : 'done'
    return ex.phase === 'answering' ? 'on' : ex.phase === 'done' || ex.phase === 'error' ? 'done' : ''
  }

  return (
    <div className="page">
      <input ref={input} type="file" accept={ACCEPT} multiple hidden onChange={(e) => { addFiles(Array.from(e.target.files ?? [])); e.target.value = '' }} />
      <div className="workspace">
        <Library
          docs={docs} off={off} uploads={uploads} history={history} activeQa={ex?.answer?.id ?? null}
          onPick={() => input.current?.click()} onFiles={addFiles} onToggle={toggle} onRemoveDoc={removeDoc} onOpenQa={openQa} onDeleteQa={deleteQa}
        />
        <main className="stage">
          <div className="stage-inner">
            {offline && <div className="alert" style={{ marginTop: 0, marginBottom: 20 }}>{offline}</div>}
            <div className="label">Archive · document retrieval</div>
            <h1 className="page-title">Ask your <em>documents.</em></h1>
            <p className="page-lede">Answers are written only from passages in the files you add, and each sentence is checked against the passage it cites.</p>

            {demo && (
              <div className="demo-banner">
                <b>Demonstration mode: retrieval is real, but the answer text is a placeholder.</b>
                <span>Add <code>GROQ_API_KEY</code> or <code>GEMINI_API_KEY</code> to <code>backend/.env</code> for written answers.</span>
              </div>
            )}

            <div className="composer">
              <textarea
                value={question}
                rows={2}
                maxLength={400}
                aria-label="Question"
                placeholder={docs.length ? 'Ask something your documents can answer' : 'Add a document to begin'}
                disabled={docs.length === 0}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask() } }}
              />
              <div className="composer-bar">
                <label className="toggle">
                  <input type="checkbox" checked={verify} onChange={(e) => setVerify(e.target.checked)} />
                  <span className="switch" />
                  Check answer against its passages
                </label>
                <span className="small muted">Searching {active.length} of {docs.length}</span>
                <button className="btn btn-solid" disabled={!canAsk} onClick={ask}>Ask</button>
              </div>
            </div>
            <p className="small muted" style={{ marginTop: 10 }}>Name the topic, and add a length or format if you like: “explain retention policy in 100 words”, “list the risks as 5 bullet points”. Search matches words, so use the terms your documents use.</p>

            {docs.length === 0 && !ex && (
              <motion.div className="empty-state" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
                <h3>Your archive is empty</h3>
                <p>Add a report, paper or set of notes. It is split into passages and indexed on this machine in a few seconds.</p>
                <button className="btn btn-solid" style={{ marginTop: 20 }} onClick={() => input.current?.click()}>Add documents</button>
              </motion.div>
            )}

            <AnimatePresence mode="wait">
              {ex && (
                <motion.div key={ex.key} style={{ marginTop: 44 }} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.4 }}>
                  <div className="label">Question</div>
                  <h2 className="run-topic" style={{ marginBottom: 20 }}>{ex.question}</h2>
                  <div className="phase">
                    <span className={phaseOf('retrieve')}>Retrieve passages</span>
                    <span className={phaseOf('answer')}>{verify ? 'Compose and check' : 'Compose'}</span>
                  </div>

                  {ex.phase === 'error' && <div className="alert">{ex.error}</div>}

                  {ex.phase === 'retrieving' && (
                    <div className="passages">
                      {[0, 1, 2].map((i) => <div key={i} className="passage"><div className="sk" style={{ width: '45%' }} /><div className="sk" /><div className="sk" style={{ width: '80%' }} /></div>)}
                    </div>
                  )}

                  {ex.phase === 'done' && !ex.answer && (
                    <div className="card"><div className="card-title">No matching passages</div><p className="muted" style={{ margin: 0 }}>None of the selected documents share words with this question. Try the terms the documents use, or include more documents.</p></div>
                  )}

                  {(ex.phase === 'answering' || ex.answer) && (
                    <div className="run-grid" style={{ marginTop: 0 }}>
                      <div className="col-main">
                        {ex.answer ? (
                          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                            <ReportView hideTitle bullets={ex.answer.bullets} report={ex.answer.report} sources={sources} verifying={false} onOpenSource={(id, passage) => setOpen({ id, passage: passage ?? '' })} />
                            {ex.answer.found && !!ex.answer.words && (
                              <div className="length-note">
                                {ex.answer.words} words
                                {ex.answer.target_words ? ` · you asked for ${ex.answer.target_words}` : ''}
                                {ex.answer.limited ? ' · your documents do not say enough to go longer' : ''}
                              </div>
                            )}
                          </motion.div>
                        ) : (
                          <div className="card skeleton-card">
                            <div className="sk sk-title" />
                            {[0, 1, 2].map((i) => <div key={i} className="sk" style={{ width: `${94 - i * 14}%` }} />)}
                            <div className="muted small">Writing from {ex.passages.length} passages{verify ? ' and checking each sentence' : ''}</div>
                          </div>
                        )}
                      </div>
                      <div className="col-side">
                        {ex.answer?.stats && <StatsPanel before={ex.answer.stats} after={null} settled />}
                        {ex.answer && !ex.answer.found && <div className="card"><div className="card-title">Not covered</div><p className="muted small" style={{ margin: 0 }}>The retrieved passages do not contain an answer, so nothing was claimed.</p></div>}
                      </div>
                    </div>
                  )}

                  {retrievalCards.length > 0 && (
                    <div style={{ marginTop: 36 }}>
                      <div className="rail-head"><span className="label">Retrieved passages</span><span className="count">{retrievalCards.length}</span></div>
                      <PassageGrid items={retrievalCards} onOpen={(n) => ex.answer && setOpen({ id: n, passage: '' })} />
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </main>
      </div>
      <SourceDrawer source={openSource} passage={open?.passage ?? ''} onClose={() => setOpen(null)} />
    </div>
  )
}
