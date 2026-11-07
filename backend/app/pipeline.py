import asyncio

from . import llm, search, verify
from .config import settings
from .models import Analysis, Plan, Report, Source
from .runs import Run

SOURCE_CHAR_BUDGET = 14000  # about 3.5k tokens: keeps prompts inside small free-tier per-minute limits


def _source_block(sources: list[Source], budget: int = SOURCE_CHAR_BUDGET) -> str:
    """Prompt text for all sources, sharing a fixed budget so many sources shrink evenly instead of overflowing."""
    per_source = max(300, min(1500, budget // max(1, len(sources))))
    return "\n\n".join(f"[source {s.id}] {s.title} ({s.domain})\n{s.content[:per_source]}" for s in sources)


async def _stage(run: Run, name: str, label: str, coro):
    await run.emit("stage", {"name": name, "label": label, "state": "running"})
    result = await coro
    await run.emit("stage", {"name": name, "label": label, "state": "done"})
    return result


async def _plan(run: Run) -> list[str]:
    if run.mode == "single":
        return [run.topic]
    plan = await llm.call_json(
        "plan",
        f"You are a research planner. Break the topic into at most {settings.max_subquestions} distinct, "
        'searchable research questions. Return {"questions":[...]}.',
        run.topic,
        Plan,
        run.usage,
        mock_ctx={"topic": run.topic},
    )
    return plan.questions[: settings.max_subquestions]


async def _research(run: Run, questions: list[str]) -> list[Source]:
    sources: dict[str, Source] = {}
    sem = asyncio.Semaphore(settings.search_concurrency)

    async def one(q: str):
        async with sem:
            await run.emit("research_query", {"question": q})
            try:
                results = await search.search(q, run.usage)
            except llm.BudgetExceeded:
                await run.emit("note", {"text": "Search budget reached; continuing with what was found."})
                return
            for r in results:
                if r["url"] in sources:
                    continue
                domain = search.domain_of(r["url"])
                quality, reason = search.score_domain(domain)
                src = Source(
                    id=len(sources) + 1,
                    title=r["title"],
                    url=r["url"],
                    domain=domain,
                    content=r["content"],
                    quality=quality,
                    quality_reason=reason,
                )
                sources[r["url"]] = src
                await run.emit("source", {**src.model_dump(), "question": q})
            await asyncio.sleep(0.4 if settings.mock_search else 0)  # lets the UI show progress in demo mode

    await asyncio.gather(*(one(q) for q in questions))
    return list(sources.values())


async def _analyze(run: Run, sources: list[Source]) -> Analysis:
    analysis = await llm.call_json(
        "analyze",
        "You are a data analyst. From the sources extract the key findings, preserving exact figures, and cite "
        "source ids. Identify CONFLICTS where sources give different numbers or opposing claims, and explain the "
        'most likely reason (definition, date, scope). Return {"findings":[{"text","source_ids"}],'
        '"conflicts":[{"topic","claims":[{"source_id","claim"}],"explanation"}]}.',
        f"Topic: {run.topic}\n\n{_source_block(sources)}",
        Analysis,
        run.usage,
        mock_ctx={"topic": run.topic, "sources": [s.model_dump() for s in sources]},
    )
    for f in analysis.findings:
        await run.emit("finding", f.model_dump())
        await asyncio.sleep(0.15 if settings.mock_llm else 0)
    for c in analysis.conflicts:
        await run.emit("conflict", c.model_dump())
    return analysis


async def _write(run: Run, sources: list[Source], analysis: Analysis | None) -> Report:
    findings = ""
    if analysis:
        findings = "\n\nKEY FINDINGS:\n" + "\n".join(f"- {f.text} {f.source_ids}" for f in analysis.findings)
        if analysis.conflicts:
            findings += "\n\nCONFLICTS TO ADDRESS:\n" + "\n".join(
                f"- {c.topic}: {c.explanation}" for c in analysis.conflicts
            )
    stage = "write" if run.mode == "multi" else "single"
    report = await llm.call_json(
        stage,
        "You are a research writer. Write a structured report with 3 sections using ONLY the provided sources. "
        "Each sentence must make exactly one factual claim and list the integer source_ids it relies on. "
        "Never add facts that are not in the sources. Be concise. Return "
        '{"title","sections":[{"heading","sentences":[{"text","source_ids"}]}]}.',
        f"Topic: {run.topic}{findings}\n\nSOURCES:\n{_source_block(sources)}",
        Report,
        run.usage,
        model=settings.writer_model,
        mock_ctx={"topic": run.topic, "sources": [s.model_dump() for s in sources]},
    )
    n = 0
    for sec in report.sections:
        for s in sec.sentences:
            n += 1
            s.id = f"s{n}"
    return report


async def execute(run: Run) -> None:
    questions = await _stage(run, "plan", "Planning research", _plan(run))
    await run.emit("plan", {"questions": questions})

    if run.require_approval and run.mode == "multi":
        questions = await run.wait_for_approval(questions)

    sources = await _stage(run, "research", "Searching sources", _research(run, questions))
    if not sources:
        raise RuntimeError("No sources were found for this topic.")

    analysis = None
    if run.mode == "multi":
        analysis = await _stage(run, "analyze", "Analysing findings", _analyze(run, sources))

    report = await _stage(run, "write", "Writing report", _write(run, sources, analysis))
    await run.emit("report", report.model_dump())

    async def on_verdict(s):
        await run.emit("verdict", {"id": s.id, "verdict": s.verdict, "evidence": s.evidence, "source_id": s.evidence_source_id})

    # Both modes are verified so the single-agent baseline can be measured fairly.
    # Only multi-agent mode then repairs what the verifier flagged.
    await _stage(run, "verify", "Fact-checking claims", verify.verify_report(report, sources, run.usage, run.topic, on_verdict))
    before = verify.compute_stats(report)
    sentences = sum(len(sec.sentences) for sec in report.sections)
    if before.unchecked and before.unchecked >= sentences / 2:
        raise RuntimeError("Fact-checking failed for most claims (the judge's replies were unreadable). Please retry.")
    if before.unchecked:
        await run.emit("note", {"text": f"{before.unchecked} claim(s) could not be checked and are left unscored."})
    await run.emit("stats", {"phase": "before", **before.model_dump(), "faithfulness": before.faithfulness})

    if run.mode == "multi":
        applied = await _stage(run, "revise", "Correcting flagged claims", verify.revise_report(report, sources, run.usage, run.topic))
        if not applied and (before.contradicted or before.unsupported):
            await run.emit("note", {"text": "Most claims failed verification, so the draft is shown unchanged with flags instead of being cut down."})
        await run.emit("report", report.model_dump())
        after = verify.compute_stats(report)
        await run.emit("stats", {"phase": "after", **after.model_dump(), "faithfulness": after.faithfulness})

    run.sources = sources
    run.analysis = analysis
    run.report = report
    run.stats = verify.compute_stats(report)
