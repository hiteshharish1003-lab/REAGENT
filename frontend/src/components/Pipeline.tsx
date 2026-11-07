import { motion } from 'framer-motion'
import { STAGES } from '../useRun'
import type { Mode, RunState } from '../types'

export default function Pipeline({ mode, state }: { mode: Mode; state: RunState }) {
  const steps = STAGES[mode]
  const doneCount = steps.filter((s) => state.stages[s.name] === 'done').length
  const waiting = state.status === 'awaiting_approval'

  return (
    <div className="pipeline">
      <div className="pipe-track">
        <motion.div
          className="pipe-fill"
          animate={{ width: `${(doneCount / (steps.length - 1 || 1)) * 100}%` }}
          transition={{ type: 'spring', stiffness: 80, damping: 18 }}
        />
      </div>
      {steps.map((s, i) => {
        const st = state.stages[s.name]
        const paused = waiting && st === 'done' && s.name === 'plan'
        return (
          <div key={s.name} className={`pipe-step ${st} ${paused ? 'paused' : ''}`}>
            <motion.div className="pipe-dot" animate={st === 'running' ? { scale: [1, 1.18, 1] } : { scale: 1 }} transition={{ repeat: st === 'running' ? Infinity : 0, duration: 1.4 }}>
              {i + 1}
            </motion.div>
            <span>{s.label}</span>
          </div>
        )
      })}
    </div>
  )
}
