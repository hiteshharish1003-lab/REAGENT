import { useState } from 'react'
import { motion } from 'framer-motion'
import type { Mode } from '../types'

const EXAMPLES = [
  'Electric vehicle adoption in India',
  'Impact of GLP-1 drugs on the food industry',
  'State of solid-state batteries',
  'Remote work and city real estate',
]

interface Props {
  busy: boolean
  demo: boolean
  onSubmit: (topic: string, mode: Mode, approval: boolean) => void
}

export default function ResearchComposer({ busy, demo, onSubmit }: Props) {
  const [topic, setTopic] = useState('')
  const [mode, setMode] = useState<Mode>('multi')
  const [approval, setApproval] = useState(true)
  const ok = topic.trim().length >= 3 && !busy
  const submit = () => ok && onSubmit(topic.trim(), mode, approval)

  return (
    <div>
      <div className="label">Inquiry · multi-agent research</div>
      <h1 className="page-title">What should we <em>establish?</em></h1>
      <p className="page-lede">State a topic. A planner proposes the questions, you approve them, and a researched report comes back with every sentence checked against its source.</p>

      {demo && (
        <div className="demo-banner">
          <b>Demonstration mode: answers are placeholders and do not depend on your question.</b>
          <span>For real results, add <code>GEMINI_API_KEY</code> and <code>TAVILY_API_KEY</code> to <code>backend/.env</code>, then restart the backend.</span>
        </div>
      )}

      <div className="composer">
        <textarea
          value={topic}
          placeholder="Describe the topic to research"
          rows={2}
          maxLength={300}
          aria-label="Research topic"
          onChange={(e) => setTopic(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
        />
        <div className="composer-bar">
          <div className="seg" role="group" aria-label="Architecture">
            <button className={mode === 'multi' ? 'on' : ''} onClick={() => setMode('multi')} title="Planner, researcher, analyst, writer, fact-checker">
              {mode === 'multi' && <motion.span layoutId="mode-thumb" className="thumb" />}
              Multi-agent
            </button>
            <button className={mode === 'single' ? 'on' : ''} onClick={() => setMode('single')} title="One-shot baseline, for comparison">
              {mode === 'single' && <motion.span layoutId="mode-thumb" className="thumb" />}
              Single agent
            </button>
          </div>
          <label className={`toggle ${mode === 'single' ? 'disabled' : ''}`}>
            <input type="checkbox" checked={approval && mode === 'multi'} disabled={mode === 'single'} onChange={(e) => setApproval(e.target.checked)} />
            <span className="switch" />
            Review plan first
          </label>
          <button className="btn btn-solid" disabled={!ok} onClick={submit}>Begin inquiry</button>
        </div>
      </div>

      <div className="chips">
        {EXAMPLES.map((e, i) => (
          <motion.button key={e} className="chip" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 + i * 0.06 }} onClick={() => setTopic(e)}>
            {e}
          </motion.button>
        ))}
      </div>
    </div>
  )
}
