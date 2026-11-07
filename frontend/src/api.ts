import type { DocAnswer, DocInfo, Mode, Passage, QaSummary, RunSummary } from './types'

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error((await res.text()) || res.statusText)
  return res.json()
}

export const api = {
  health: () => fetch('/api/health').then((r) => json<{ mock_llm: boolean; mock_search: boolean }>(r)),
  listRuns: () => fetch('/api/runs').then((r) => json<RunSummary[]>(r)),
  createRun: (topic: string, mode: Mode, requireApproval: boolean) =>
    fetch('/api/runs', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ topic, mode, require_approval: requireApproval }),
    }).then((r) => json<{ id: string }>(r)),
  approve: (id: string, questions: string[]) =>
    fetch(`/api/runs/${id}/approve`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ questions }),
    }).then((r) => json<{ ok: boolean }>(r)),
  deleteRun: (id: string) => fetch(`/api/runs/${id}`, { method: 'DELETE' }).then((r) => json<{ ok: boolean }>(r)),

  // ---- document engine ----
  listDocs: () => fetch('/api/docs').then((r) => json<DocInfo[]>(r)),
  deleteDoc: (id: number) => fetch(`/api/docs/${id}`, { method: 'DELETE' }).then((r) => json<{ ok: boolean }>(r)),
  /** Upload with progress. The file bytes are the request body; the server indexes before replying. */
  uploadDoc: (file: File, onProgress: (fraction: number) => void) =>
    new Promise<DocInfo>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', `/api/docs?name=${encodeURIComponent(file.name)}`)
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total)
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) return resolve(JSON.parse(xhr.responseText))
        let msg = xhr.responseText
        try { msg = JSON.parse(msg).detail ?? msg } catch { /* plain text */ }
        reject(new Error(msg || xhr.statusText))
      }
      xhr.onerror = () => reject(new Error('Upload failed. Is the backend running?'))
      xhr.send(file)
    }),
  retrieve: (question: string, docIds: number[]) =>
    fetch('/api/docs/retrieve', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ question, doc_ids: docIds }),
    }).then((r) => json<{ passages: Passage[] }>(r)),
  answer: (question: string, passageIds: number[], verify: boolean) =>
    fetch('/api/docs/answer', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ question, passage_ids: passageIds, verify }),
    }).then(async (r) => {
      if (!r.ok) {
        let msg = await r.text()
        try { msg = JSON.parse(msg).detail ?? msg } catch { /* plain text */ }
        throw new Error(msg || r.statusText)
      }
      return r.json() as Promise<DocAnswer>
    }),
  qaHistory: () => fetch('/api/docs/history').then((r) => json<QaSummary[]>(r)),
  qaItem: (id: number) => fetch(`/api/docs/history/${id}`).then((r) => json<DocAnswer>(r)),
  qaDelete: (id: number) => fetch(`/api/docs/history/${id}`, { method: 'DELETE' }).then((r) => json<{ ok: boolean }>(r)),
}
