import asyncio
import re

from . import llm
from .config import settings
from .models import Report, Revisions, Section, Source, Verification, VerifyStats

BATCH = 20  # one call for a typical report; fewer requests matter on free-tier daily quotas
STOP = {"that", "this", "with", "from", "have", "were", "which", "their", "will", "been", "than", "into"}


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", text.lower()) if w not in STOP}


def _near_duplicate(a: str, b: str, threshold: float = 0.7) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta and tb) and len(ta & tb) / len(ta | tb) >= threshold


def rewrite_is_faithful(original: str, new: str, verdict: str) -> bool:
    """Guard against a "correction" that quietly becomes a different claim.

    An unsupported claim may only be trimmed: nearly every word of the result must come from the original.
    A contradicted claim may change figures, but must stay about the same subject as the original.
    """
    to, tn = _tokens(original), _tokens(new)
    if not to or not tn:
        return False
    if verdict == "unsupported":
        return len(tn & to) / len(tn) >= 0.8
    return len(to & tn) / len(to) >= 0.5


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]


def best_passages(claim: str, sources: list[Source], k: int = 2) -> list[dict]:
    """Lexical shortlist: the k source sentences that overlap most with the claim.

    Keeps the judge prompt tiny (cheap, fast) instead of sending whole documents.
    """
    ct = _tokens(claim)
    scored = []
    for s in sources:
        for sent in split_sentences(s.content):
            st = _tokens(sent)
            if not st:
                continue
            scored.append((len(ct & st) / max(1, len(ct)), s.id, sent))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"source_id": sid, "text": sent} for _, sid, sent in scored[:k]]


def _passages_for(sentence, by_id: dict[int, Source]) -> list[dict]:
    cited = [by_id[i] for i in sentence.source_ids if i in by_id]
    # If the writer cited nothing (or something invalid), search everything: that is itself a signal.
    return best_passages(sentence.text, cited or list(by_id.values()))


def normalize_verdict(raw) -> str | None:
    """Map whatever wording the model used onto our three verdicts; None if it is unreadable."""
    v = str(raw or "").lower().replace("_", " ").strip()
    if "contradict" in v:
        return "contradicted"
    if any(w in v for w in ("unsupport", "not support", "partial", "unverif", "insufficient", "no evidence")):
        return "unsupported"
    if "support" in v:
        return "supported"
    return None


def normalize_source_id(raw) -> int | None:
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    m = re.search(r"\d+", str(raw or ""))  # models often answer "source 3" instead of 3
    return int(m.group()) if m else None


def _nid(raw) -> str:
    return re.sub(r"[^a-z0-9]", "", str(raw).lower())  # "[S1]", "s1" and " s1 " are the same claim


async def verify_report(report: Report, sources: list[Source], usage: llm.Usage, topic: str, on_verdict=None) -> None:
    """Judge every sentence. A sentence the judge cannot be made to answer keeps verdict=None ("unchecked")
    instead of being guessed as unsupported, which would silently delete good content."""
    by_id = {s.id: s for s in sources}
    sentences = [s for sec in report.sections for s in sec.sentences]
    sem = asyncio.Semaphore(3)  # batches are independent, so judge them concurrently

    async def ask(batch) -> dict[str, dict]:
        items = [{"id": s.id, "text": s.text, "passages": _passages_for(s, by_id)} for s in batch]
        user = "Judge each claim using ONLY its passages.\n" + "\n".join(
            f"[{it['id']}] CLAIM: {it['text']}\n"
            + "\n".join(f"   (source {p['source_id']}) {p['text']}" for p in it["passages"])
            for it in items
        )
        async with sem:
            result = await llm.call_json(
                "verify",
                "You are a strict fact-checker. Break each claim into its parts (every number, date, name, "
                "direction and qualifier). 'supported' ONLY if EVERY part is stated in a passage. "
                "'contradicted' if any part conflicts with a passage (different number, opposite direction, wrong "
                "attribution). Otherwise 'unsupported', including when only part of the claim is stated. "
                "verdict must be exactly one of: supported, contradicted, unsupported. "
                "evidence = the exact passage text relied on; for an unsupported claim, give the closest passage "
                "that covers part of it (or empty if none). source_id = that passage's integer source number, or "
                'null. Return one entry per claim id: {"verdicts":[{"id","verdict","evidence","source_id"}]}.',
                user,
                Verification,
                usage,
                mock_ctx={"stage": "verify", "items": items, "topic": topic},
            )
        return {_nid(v.get("id")): v for v in result.verdicts if isinstance(v, dict)}

    def readable(got: dict, sent) -> bool:
        return normalize_verdict((got.get(_nid(sent.id)) or {}).get("verdict")) is not None

    async def judge(batch):
        got = await ask(batch)
        missing = [s for s in batch if not readable(got, s)]
        if missing:  # one retry for just the claims the judge skipped or answered unreadably
            got.update(await ask(missing))
        for s in batch:
            v = got.get(_nid(s.id)) or {}
            s.verdict = normalize_verdict(v.get("verdict"))
            s.evidence = (v.get("evidence") or "") if s.verdict else ""
            s.evidence_source_id = normalize_source_id(v.get("source_id")) if s.verdict else None
            if on_verdict:
                await on_verdict(s)

    await asyncio.gather(*(judge(sentences[i : i + BATCH]) for i in range(0, len(sentences), BATCH)))


def compute_stats(report: Report) -> VerifyStats:
    """`total` counts judged sentences only; unchecked ones are reported separately, not scored."""
    st = VerifyStats()
    for sec in report.sections:
        for s in sec.sentences:
            if s.action == "removed":
                continue
            if s.verdict is None:
                st.unchecked += 1
                continue
            st.total += 1
            setattr(st, s.verdict, getattr(st, s.verdict) + 1)
    return st


async def revise_report(report: Report, sources: list[Source], usage: llm.Usage, topic: str) -> bool:
    """Rewrite contradicted claims to match their evidence; drop unsupported ones; re-verify rewrites.

    Returns False if it declined to change the report (nothing flagged, or too much would be lost)."""
    flagged = [s for sec in report.sections for s in sec.sentences if s.verdict in ("contradicted", "unsupported")]
    if not flagged:
        return False
    items = [{"id": s.id, "text": s.text, "verdict": s.verdict, "evidence": s.evidence} for s in flagged]
    user = "\n".join(
        f"[{it['id']}] ({it['verdict']}) CLAIM: {it['text']}\n   EVIDENCE: {it['evidence'] or 'none found'}" for it in items
    )
    result = await llm.call_json(
        "revise",
        "Fix flagged claims in a research report. For a contradicted claim, rewrite it as one sentence that says "
        "exactly what the evidence says (keep the figures from the evidence). For an unsupported claim with "
        "evidence, keep ONLY the part the evidence states, using the claim's own words, as one sentence; never "
        "add new facts. For an unsupported claim with no "
        'evidence, return null text so it is removed. Return {"rewrites":[{"id","text"}]}.',
        user,
        Revisions,
        usage,
        model=settings.fast_model,
        mock_ctx={"stage": "revise", "items": items, "topic": topic},
    )
    rewrites = {r["id"]: r.get("text") for r in result.rewrites}
    # A corrected claim often restates a sentence the report already makes; drop the repeat.
    seen = [s.text for sec in report.sections for s in sec.sentences if s.verdict == "supported"]
    decisions: list[tuple] = []
    for s in flagged:
        new_text = rewrites.get(s.id)
        ok = (
            new_text
            and rewrite_is_faithful(s.text, new_text, s.verdict)
            and not any(_near_duplicate(new_text, t) for t in seen)
        )
        if ok:
            seen.append(new_text)
        decisions.append((s, new_text if ok else None))

    # If the verifier rejects most of the report, trust it less than the draft: keep the draft, flagged.
    total = sum(1 for sec in report.sections for s in sec.sentences)
    survivors = total - sum(1 for _, t in decisions if t is None)
    if survivors < max(2, round(total * 0.3)):
        return False

    changed = []
    for s, new_text in decisions:
        s.original = s.text
        if new_text:
            s.text, s.action = new_text, "rewritten"
            changed.append(s)
        else:
            s.action = "removed"

    # Re-judge rewrites so the "after" score is measured, not assumed. A rewrite that still fails is dropped.
    if changed:
        tmp = Report(title="", sections=[Section(heading="", sentences=changed)])
        await verify_report(tmp, sources, usage, topic)
        for s in changed:
            if s.verdict != "supported":
                s.action = "removed"
    return True
