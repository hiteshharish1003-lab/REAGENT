import { useEffect, useReducer } from 'react'
import type { Mode, RunState, ServerEvent } from './types'

const EVENT_TYPES = [
  'stage', 'plan', 'awaiting_approval', 'approved', 'research_query', 'source', 'finding',
  'conflict', 'report', 'verdict', 'stats', 'note', 'done', 'error',
]

export const STAGES: Record<Mode, { name: string; label: string }[]> = {
  multi: [
    { name: 'plan', label: 'Plan' },
    { name: 'research', label: 'Research' },
    { name: 'analyze', label: 'Analyse' },
    { name: 'write', label: 'Write' },
    { name: 'verify', label: 'Verify' },
    { name: 'revise', label: 'Correct' },
  ],
  single: [
    { name: 'plan', label: 'Plan' },
    { name: 'research', label: 'Research' },
    { name: 'write', label: 'Write' },
    { name: 'verify', label: 'Verify' },
  ],
}

function initial(mode: Mode): RunState {
  return {
    status: 'connecting',
    stages: Object.fromEntries(STAGES[mode].map((s) => [s.name, 'pending'])),
    plan: [], approvedQuestions: [], sources: [], findings: [], conflicts: [],
    report: null, before: null, after: null, usage: null, notes: [], error: null,
  }
}

type Action = { type: 'event'; ev: ServerEvent } | { type: 'reset'; mode: Mode }

function reduce(state: RunState, action: Action): RunState {
  if (action.type === 'reset') return initial(action.mode)
  const { type, data } = action.ev
  switch (type) {
    case 'stage':
      return { ...state, status: 'running', stages: { ...state.stages, [data.name]: data.state } }
    case 'plan':
      return { ...state, plan: data.questions }
    case 'awaiting_approval':
      return { ...state, status: 'awaiting_approval', plan: data.questions }
    case 'approved':
      return { ...state, status: 'running', approvedQuestions: data.questions }
    case 'source':
      return { ...state, sources: [...state.sources, data] }
    case 'finding':
      return { ...state, findings: [...state.findings, data] }
    case 'conflict':
      return { ...state, conflicts: [...state.conflicts, data] }
    case 'report':
      return { ...state, report: data }
    case 'verdict': {
      if (!state.report) return state
      const report = {
        ...state.report,
        sections: state.report.sections.map((sec) => ({
          ...sec,
          sentences: sec.sentences.map((s) =>
            s.id === data.id
              ? { ...s, verdict: data.verdict, evidence: data.evidence, evidence_source_id: data.source_id }
              : s,
          ),
        })),
      }
      return { ...state, report }
    }
    case 'stats':
      return data.phase === 'before' ? { ...state, before: data } : { ...state, after: data }
    case 'note':
      return { ...state, notes: [...state.notes, data.text] }
    case 'done':
      return { ...state, status: 'done', usage: data.usage }
    case 'error':
      return { ...state, status: 'error', error: data.message }
    default:
      return state
  }
}

export function useRun(runId: string | null, mode: Mode): RunState {
  const [state, dispatch] = useReducer(reduce, mode, initial)

  useEffect(() => {
    dispatch({ type: 'reset', mode })
    if (!runId) return
    let lastSeq = -1
    const es = new EventSource(`/api/runs/${runId}/events`)
    const handler = (e: MessageEvent) => {
      const ev: ServerEvent = JSON.parse(e.data)
      if (ev.seq <= lastSeq) return // reconnects replay from 0; ignore what we already applied
      lastSeq = ev.seq
      dispatch({ type: 'event', ev })
      if (ev.type === 'done' || ev.type === 'error') es.close()
    }
    EVENT_TYPES.forEach((t) => es.addEventListener(t, handler))
    return () => es.close()
  }, [runId, mode])

  return state
}
