"""Document engine: ingest files, retrieve passages, answer from them.

Retrieval is SQLite FTS5 with BM25 ranking. It needs no embedding model, no API quota and no extra disk, which suits a
small laptop. The trade-off is that it matches words (with stemming), not meaning, so a question phrased very
differently from the document can miss. Embeddings could be added later behind `retrieve` without touching the rest.
"""

import hashlib
import io
import json
import re
import time
from dataclasses import dataclass

from . import db, llm, verify
from .config import settings
from .models import Answer, Report, Section, Sentence, Source

MAX_BYTES = 20 * 1024 * 1024
MAX_CHUNKS = 3000
CHUNK_CHARS = 900
OVERLAP_CHARS = 150
TEXT_SUFFIXES = (".txt", ".md", ".markdown", ".csv", ".log", ".json")

STOP = {"a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "did", "do", "does", "for", "from", "had", "has", "have", "how", "i", "if", "in", "into", "is", "it", "its", "of", "on", "or", "that", "the", "their", "them", "then", "there", "these", "they", "this", "to", "was", "were", "what", "when", "where", "which", "who", "whom", "why", "will", "with", "would", "about", "your", "you", "we", "our", "not", "no", "yes", "also", "than", "so", "such"}


class IngestError(Exception):
    pass


def _extract(name: str, data: bytes) -> list[tuple[int, str]]:
    """Return [(page_number, text)]. Plain-text files count as a single page."""
    lower = name.lower()
    if lower.endswith(".pdf"):
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError

        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise IngestError("This PDF is password-protected.")
            pages = [(i + 1, (p.extract_text() or "")) for i, p in enumerate(reader.pages)]
        except IngestError:
            raise
        except (PyPdfError, ValueError, KeyError, OSError) as e:
            raise IngestError(f"Could not read this PDF ({e.__class__.__name__}).") from e
        pages = [(n, t) for n, t in pages if t.strip()]
        if not pages:
            raise IngestError("No selectable text found. Scanned PDFs need OCR first.")
        return pages
    if lower.endswith(TEXT_SUFFIXES):
        text = data.decode("utf-8", errors="replace")
        if not text.strip():
            raise IngestError("The file is empty.")
        return [(1, text)]
    raise IngestError("Unsupported file type. Use PDF, TXT, MD, CSV or JSON.")


def chunk_text(text: str) -> list[str]:
    """Pack whole sentences into ~CHUNK_CHARS chunks, carrying a short overlap so a fact split across a boundary
    is still retrievable."""
    text = re.sub(r"[ \t]+", " ", text.replace("\r", ""))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    units: list[str] = []
    for piece in re.split(r"(?<=[.!?])\s+|\n\s*\n", text):
        piece = piece.replace("\n", " ").strip()
        while len(piece) > CHUNK_CHARS * 1.5:  # text with no punctuation: cut at a space
            cut = piece.rfind(" ", 0, CHUNK_CHARS) or CHUNK_CHARS
            units.append(piece[:cut].strip())
            piece = piece[cut:].strip()
        if piece:
            units.append(piece)

    chunks: list[str] = []
    cur: list[str] = []
    size = 0
    for u in units:
        if size + len(u) > CHUNK_CHARS and cur:
            chunks.append(" ".join(cur))
            tail: list[str] = []
            tail_len = 0
            for prev in reversed(cur):
                if tail_len + len(prev) > OVERLAP_CHARS:
                    break
                tail.insert(0, prev)
                tail_len += len(prev)
            cur, size = tail, tail_len
        cur.append(u)
        size += len(u)
    if cur:
        chunks.append(" ".join(cur))
    return [c for c in chunks if len(c) > 30]


def ingest(name: str, data: bytes) -> dict:
    name = name.strip().split("/")[-1][:200] or "document"
    sha = hashlib.sha1(data).hexdigest()
    with db.conn() as c:
        existing = c.execute("SELECT * FROM documents WHERE sha=?", (sha,)).fetchone()
        if existing:
            return {**dict(existing), "duplicate": True}

    pages = _extract(name, data)
    rows: list[tuple[int, str]] = []
    for page, text in pages:
        rows.extend((page, ch) for ch in chunk_text(text))
    if not rows:
        raise IngestError("The file has too little text to index.")
    if len(rows) > MAX_CHUNKS:
        raise IngestError(f"Too large to index on this machine ({len(rows)} passages; the limit is {MAX_CHUNKS}).")

    with db.conn() as c:
        cur = c.execute(
            "INSERT INTO documents (name, sha, pages, chars, chunks, created_at) VALUES (?,?,?,?,?,?)",
            (name, sha, len(pages), sum(len(t) for _, t in pages), len(rows), time.time()),
        )
        doc_id = cur.lastrowid
        for i, (page, text) in enumerate(rows):
            cid = c.execute(
                "INSERT INTO chunks (doc_id, ord, page, text) VALUES (?,?,?,?)", (doc_id, i, page, text)
            ).lastrowid
            c.execute("INSERT INTO chunk_fts (rowid, text) VALUES (?,?)", (cid, text))
        doc = c.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    return {**dict(doc), "duplicate": False}


def list_documents() -> list[dict]:
    with db.conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()]


def delete_document(doc_id: int) -> None:
    with db.conn() as c:
        ids = [r["id"] for r in c.execute("SELECT id FROM chunks WHERE doc_id=?", (doc_id,)).fetchall()]
        c.executemany("DELETE FROM chunk_fts WHERE rowid=?", [(i,) for i in ids])
        c.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
        c.execute("DELETE FROM documents WHERE id=?", (doc_id,))


# Words that describe HOW to answer, not WHAT to look for. Searching for them only adds noise.
INSTRUCTION = {
    "explain", "describe", "summarise", "summarize", "summary", "overview", "elaborate", "discuss", "outline",
    "tell", "give", "write", "please", "brief", "briefly", "short", "concise", "detail", "detailed", "details",
    "words", "word", "sentence", "sentences", "bullet", "bullets", "point", "points", "line", "lines",
    "paragraph", "paragraphs", "list", "topic", "certain", "specific", "me", "exactly", "around", "roughly",
    "approximately", "maximum", "minimum", "least", "most", "within", "under", "using", "based", "document",
    "documents", "file", "files", "uploaded",
}
_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_LENGTH_PHRASE = re.compile(
    r"\b(\d{1,4}|one|two|three|four|five|six|seven|eight|nine|ten|a)\s*-?\s*(words?|sentences?|bullets?|points?|lines?)\b"
)


@dataclass
class Brief:
    """What the user asked for beyond the topic: a length, a format, or a broad overview."""

    words: int | None = None
    sentences: int | None = None
    bullets: bool = False
    broad: bool = False


def parse_brief(question: str) -> Brief:
    low = question.lower()
    b = Brief()
    for m in _LENGTH_PHRASE.finditer(low):
        n = int(m.group(1)) if m.group(1).isdigit() else _NUMBER_WORDS.get(m.group(1), 1)
        unit = m.group(2)
        if unit.startswith("word") and n >= 15:
            b.words = min(n, 600)
        elif unit.startswith(("sentence", "line")):
            b.sentences = max(1, min(n, 15))
        elif unit.startswith(("bullet", "point")):
            b.sentences, b.bullets = max(1, min(n, 15)), True
    b.bullets = b.bullets or bool(re.search(r"\bbullet|\bas a list\b|\bin points\b", low))
    b.broad = bool(re.search(r"summar|overview|explain|describe|elaborate|outline|discuss|in detail", low)) or (b.words or 0) >= 150
    return b


def _topic_terms(question: str) -> list[str]:
    low = _LENGTH_PHRASE.sub(" ", question.lower())
    words = [w for w in re.findall(r"[a-z0-9]{2,}", low) if w not in STOP and w not in INSTRUCTION]
    return list(dict.fromkeys(words))[:12]


def _match_query(question: str) -> str:
    return " OR ".join(f'"{w}"' for w in _topic_terms(question))


def _overview(doc_ids: list[int] | None, k: int) -> list[dict]:
    """No topic words (e.g. "summarise this in 100 words"): take the opening passages, one document at a time."""
    sql = "SELECT c.id, c.doc_id, c.page, c.text, d.name FROM chunks c JOIN documents d ON d.id = c.doc_id"
    args: list = []
    if doc_ids:
        sql += f" WHERE c.doc_id IN ({','.join('?' * len(doc_ids))})"
        args += doc_ids
    sql += " ORDER BY c.ord, c.doc_id LIMIT ?"
    with db.conn() as c:
        rows = [dict(r) for r in c.execute(sql, [*args, k]).fetchall()]
    for r in rows:
        r["relevance"] = 1.0
    return rows


def retrieve(question: str, doc_ids: list[int] | None = None, k: int | None = None) -> list[dict]:
    brief = parse_brief(question)
    if k is None:  # overviews and long answers need more material than a pinpoint question
        k = 10 if (brief.words or 0) >= 200 else 8 if brief.broad else 6
    match = _match_query(question)
    if not match:
        return _overview(doc_ids, k) if (brief.broad or brief.words or brief.sentences) else []
    sql = (
        "SELECT c.id, c.doc_id, c.page, c.text, d.name, bm25(chunk_fts) AS score "
        "FROM chunk_fts JOIN chunks c ON c.id = chunk_fts.rowid JOIN documents d ON d.id = c.doc_id "
        "WHERE chunk_fts MATCH ?"
    )
    args: list = [match]
    if doc_ids:
        sql += f" AND c.doc_id IN ({','.join('?' * len(doc_ids))})"
        args += doc_ids
    sql += " ORDER BY score LIMIT ?"
    args.append(k)
    with db.conn() as c:
        rows = [dict(r) for r in c.execute(sql, args).fetchall()]
    best = abs(rows[0]["score"]) if rows else 0
    for r in rows:
        r["relevance"] = round(abs(r.pop("score")) / best, 3) if best else 0.0
    return rows


def _chunks_by_id(ids: list[int]) -> list[dict]:
    with db.conn() as c:
        rows = c.execute(
            f"SELECT c.id, c.doc_id, c.page, c.text, d.name FROM chunks c JOIN documents d ON d.id=c.doc_id "
            f"WHERE c.id IN ({','.join('?' * len(ids))})",
            ids,
        ).fetchall()
    by = {r["id"]: dict(r) for r in rows}
    return [by[i] for i in ids if i in by]


async def answer(question: str, passage_ids: list[int], do_verify: bool) -> dict:
    chunks = _chunks_by_id(passage_ids)
    if not chunks:
        raise IngestError("Those passages no longer exist. Ask again.")
    # Passages become numbered sources so the existing claim verifier can judge the answer unchanged.
    sources = [
        Source(
            id=i + 1,
            title=f"{ch['name']}, p. {ch['page']}",
            url=f"doc:{ch['doc_id']}",
            domain=ch["name"],
            content=ch["text"],
            quality=1.0,
            quality_reason=f"Your document, page {ch['page']}",
        )
        for i, ch in enumerate(chunks)
    ]
    usage = llm.Usage()
    brief = parse_brief(question)
    block = "\n\n".join(f"[passage {s.id}] {s.title}\n{s.content}" for s in sources)
    available = sum(len(s.content.split()) for s in sources)
    valid = {s.id for s in sources}

    def length_rule() -> str:
        if brief.words:
            lo, hi = round(brief.words * 0.9), round(brief.words * 1.1)
            n = max(2, min(16, round(brief.words / 22)))
            return (
                f"LENGTH: the whole answer must be {lo} to {hi} words in total (target {brief.words}), about {n} "
                "sentences. Count the words before answering; do not run short or long. Lead with a direct "
                "statement of the topic, then develop it."
            )
        if brief.sentences:
            return f"LENGTH: write exactly {brief.sentences} sentence(s)."
        return "LENGTH: write 2 to 6 short sentences."

    system = (
        "Answer the question using ONLY the numbered passages. Each sentence makes one factual claim and lists the "
        "integer passage numbers it relies on in source_ids. Never add facts that are not in the passages, and "
        "do not pad to reach a length. Follow any instruction about style or format in the question. "
        + length_rule()
        + (" Each sentence is one bullet point." if brief.bullets else "")
        + " If the passages do not contain the answer, set found to false and write one sentence saying so, with no "
        'source_ids. Return {"found":bool,"sentences":[{"text","source_ids"}]}.'
    )
    user = f"Question: {question}\n\nPASSAGES:\n{block}"
    mock_ctx = {"topic": question, "sources": [s.model_dump() for s in sources]}

    async def generate(extra: str = "") -> tuple[Answer, int]:
        res = await llm.call_json(
            "ask", system, user + extra, Answer, usage, model=settings.writer_model, mock_ctx=mock_ctx
        )
        return res, sum(len(x.text.split()) for x in res.sentences)

    result, wc = await generate()
    limited = False
    if brief.words and result.found:
        off = abs(wc - brief.words) / brief.words > 0.2
        if off and wc < brief.words and available < brief.words * 1.5:
            limited = True  # the documents simply do not say enough; padding would mean inventing
        elif off and not settings.mock_llm:
            draft = " ".join(x.text for x in result.sentences)
            retry, wc2 = await generate(
                f"\n\nYour previous draft was {wc} words, but {brief.words} were requested (allowed "
                f"{round(brief.words * 0.9)} to {round(brief.words * 1.1)}). Rewrite it to that length, still using "
                f"only the passages.\nPREVIOUS DRAFT:\n{draft}"
            )
            if abs(wc2 - brief.words) < abs(wc - brief.words):
                result, wc = retry, wc2

    sentences = [
        Sentence(id=f"s{n + 1}", text=s.text.strip(), source_ids=[i for i in s.source_ids if i in valid])
        for n, s in enumerate(result.sentences)
        if s.text.strip()
    ]
    report = Report(title=question, sections=[Section(heading="Answer", sentences=sentences)])

    stats = None
    if do_verify and result.found and sentences:
        await verify.verify_report(report, sources, usage, question)
        stats = verify.compute_stats(report)

    out = {
        "question": question,
        "found": result.found,
        "report": report.model_dump(),
        "sources": [s.model_dump() for s in sources],
        "stats": {**stats.model_dump(), "faithfulness": stats.faithfulness} if stats else None,
        "usage": usage.as_dict(),
        "words": sum(len(x.text.split()) for x in sentences),
        "target_words": brief.words,
        "bullets": brief.bullets,
        "limited": limited,
    }
    with db.conn() as c:
        out["id"] = c.execute(
            "INSERT INTO doc_qa (question, result, created_at) VALUES (?,?,?)", (question, json.dumps(out), time.time())
        ).lastrowid
    return out


def history(limit: int = 30) -> list[dict]:
    with db.conn() as c:
        rows = c.execute("SELECT id, question, created_at FROM doc_qa ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_qa(qa_id: int) -> dict | None:
    with db.conn() as c:
        row = c.execute("SELECT result FROM doc_qa WHERE id=?", (qa_id,)).fetchone()
    return json.loads(row["result"]) if row else None


def delete_qa(qa_id: int) -> None:
    with db.conn() as c:
        c.execute("DELETE FROM doc_qa WHERE id=?", (qa_id,))
