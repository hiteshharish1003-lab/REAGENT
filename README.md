# REAGENT: documents and research, verified

One site, two engines, each on its own page. Both write only from evidence and then **check every sentence against
its source**, correcting or removing what the sources don't support.

| Engine | Page | What it does |
|---|---|---|
| **Archive** | `#/archive` | Upload PDF/TXT/MD/CSV/JSON files, ask questions, get an answer built only from your pages. Every sentence cites a passage and is verified. Documents and past questions persist locally. |
| **Inquiry** | `#/inquiry` | Multi-agent web research: plan, you approve, research, analyse, write, verify, correct. Surfaces conflicts between sources. |

```
Inquiry:  plan → (you approve) → research → analyse → write → verify → correct
Archive:  retrieve passages → compose from them → verify each sentence
```

**Archive retrieval** is SQLite FTS5 with BM25 ranking: no embedding model, no extra API quota, no extra disk. It
matches words (with stemming), not meaning, so questions work best phrased with the terms the documents use.
Archive understands requests about length and format, for example "explain legal holds in 100 words", "summarise
this in 60 words" or "list the recommendations as 4 bullet points". Instruction words are not searched, only the
topic is, and the answer is checked against the requested length (with one retry if it is more than 20% off).
Answers go to Groq first so Gemini's small daily quota is kept for Inquiry.

## Run it

```bash
# backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # add keys (below); blank = demo mode with canned data
.venv/bin/uvicorn app.main:app --port 8000

# frontend (second terminal)
cd frontend && npm install && npm run dev      # http://localhost:5173
```

### Keys (all free, no card)

| Key | Where | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | aistudio.google.com/apikey | LLM |
| `GROQ_API_KEY` | console.groq.com/keys | LLM fallback when Gemini's daily quota ends |
| `TAVILY_API_KEY` | tavily.com | web search |

Free tiers have small daily quotas (Gemini: ~20 requests/day/model). A run uses 4-7 requests, and the app moves
to the next model/provider automatically. Anthropic (`ANTHROPIC_API_KEY`) is supported and used instead if set.

## Evaluate it

```bash
cd backend
.venv/bin/python -m evals.run_eval --n 3                  # single-agent vs multi-agent on 3 questions
.venv/bin/python -m evals.run_eval --start 5 --n 2 --modes multi
```

Reports faithfulness before/after correction, how much content survived, time and tokens, in `evals/results/`.
Scores come from an LLM judge, not humans; use them to compare modes, not as absolute accuracy.

## Check it

```bash
cd backend && .venv/bin/ruff check app evals tests && .venv/bin/python -m pytest -q tests
cd frontend && npx tsc -b && npm run lint && npm run build
```

## Design notes

- **Verification is conservative.** A claim is "supported" only if every number, date and name is in a passage.
  A claim the judge can't be made to answer stays *unchecked* rather than being guessed and deleted.
- **Corrections can't change the subject.** A rewrite must reuse the original claim's words (trim) or stay on its
  subject (fix a number), is re-verified, and is dropped if it still fails. If the verifier rejects most of a
  report, the draft is shown flagged instead of being cut down.
- **Built for a small laptop.** SQLite, no Docker, one run at a time, disk-cached search, prompt size budgets.
