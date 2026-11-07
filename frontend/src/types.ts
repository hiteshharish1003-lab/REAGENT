export type Verdict = 'supported' | 'contradicted' | 'unsupported'
export type StageState = 'pending' | 'running' | 'done'
export type Mode = 'multi' | 'single'

export interface Source {
  id: number
  title: string
  url: string
  domain: string
  content: string
  quality: number
  quality_reason: string
  question?: string
}

export interface Sentence {
  id: string
  text: string
  source_ids: number[]
  verdict: Verdict | null
  evidence: string
  evidence_source_id: number | null
  original: string
  action: 'kept' | 'rewritten' | 'removed'
}

export interface Report {
  title: string
  sections: { heading: string; sentences: Sentence[] }[]
}

export interface Finding {
  text: string
  source_ids: number[]
}

export interface Conflict {
  topic: string
  claims: { source_id: number; claim: string }[]
  explanation: string
}

export interface Stats {
  phase?: 'before' | 'after'
  total: number
  supported: number
  contradicted: number
  unsupported: number
  unchecked?: number
  faithfulness: number
}

export interface Usage {
  input_tokens: number
  output_tokens: number
  calls: number
  searches: number
  cost_usd: number
  seconds?: number
}

export interface RunSummary {
  id: string
  topic: string
  mode: Mode
  status: string
  created_at: number
  stats: Stats | null
}

export interface RunState {
  status: 'connecting' | 'running' | 'awaiting_approval' | 'done' | 'error'
  stages: Record<string, StageState>
  plan: string[]
  approvedQuestions: string[]
  sources: Source[]
  findings: Finding[]
  conflicts: Conflict[]
  report: Report | null
  before: Stats | null
  after: Stats | null
  usage: Usage | null
  notes: string[]
  error: string | null
}

export interface ServerEvent {
  seq: number
  type: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any
  ts: number
}

export interface DocInfo {
  id: number
  name: string
  pages: number
  chars: number
  chunks: number
  created_at: number
  duplicate?: boolean
}

export interface Passage {
  id: number
  doc_id: number
  page: number
  text: string
  name: string
  relevance: number
}

export interface DocAnswer {
  id: number
  question: string
  found: boolean
  report: Report
  sources: Source[]
  stats: Stats | null
  usage: { calls: number; input_tokens: number; output_tokens: number }
  words?: number
  target_words?: number | null
  bullets?: boolean
  limited?: boolean
}

export interface QaSummary {
  id: number
  question: string
  created_at: number
}
