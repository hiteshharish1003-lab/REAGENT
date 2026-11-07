"""Compare the single-agent baseline with the multi-agent pipeline on the same questions.

    python -m evals.run_eval --n 5                 # first 5 questions, both modes
    python -m evals.run_eval --n 3 --modes multi   # one mode only

Every run is also saved to the app's history, so you can open it in the UI and inspect each verdict.
Free-tier APIs have daily quotas: one question in both modes costs about 10-12 model calls.
"""

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

from app import db
from app.models import RunRequest
from app.runs import manager

HERE = Path(__file__).parent


def _metrics(run, seconds: float) -> dict:
    before = next((e["data"] for e in run.events if e["type"] == "stats" and e["data"]["phase"] == "before"), None)
    after = next((e["data"] for e in run.events if e["type"] == "stats" and e["data"]["phase"] == "after"), None) or before
    error = next((e["data"]["message"] for e in run.events if e["type"] == "error"), None)
    if error or not before:
        return {"error": error or "no stats produced", "seconds": round(seconds, 1)}
    sentences = [s for sec in (run.report.sections if run.report else []) for s in sec.sentences]
    return {
        "sources": len(run.sources),
        "claims_written": before["total"],
        "faith_before": before["faithfulness"],
        "faith_after": after["faithfulness"],
        # Share of written claims still in the final report: guards against "fixing" accuracy by deleting content.
        "kept_ratio": round(after["total"] / before["total"], 3) if before["total"] else 0.0,
        "rewritten": sum(1 for s in sentences if s.action == "rewritten"),
        "removed": sum(1 for s in sentences if s.action == "removed"),
        "conflicts_found": sum(1 for e in run.events if e["type"] == "conflict"),
        "seconds": round(seconds, 1),
        "calls": run.usage.calls,
        "tokens": run.usage.input_tokens + run.usage.output_tokens,
    }


async def run_one(topic: str, mode: str) -> dict:
    run = manager.start(RunRequest(topic=topic, mode=mode, require_approval=False))
    t0 = time.time()
    async for _ in run.stream():
        pass
    return {"topic": topic, "mode": mode, "run_id": run.id, **_metrics(run, time.time() - t0)}


def _mean(rows: list[dict], key: str) -> float | None:
    vals = [r[key] for r in rows if key in r]
    return round(statistics.mean(vals), 3) if vals else None


def _report(results: list[dict]) -> str:
    lines = ["# Eval results", "", f"Questions: {len({r['topic'] for r in results})} · runs: {len(results)}", ""]
    lines += ["| Mode | Runs ok | Faithfulness before | Faithfulness after | Claims kept | Seconds | Tokens |", "|---|---|---|---|---|---|---|"]
    for mode in ("single", "multi"):
        rows = [r for r in results if r["mode"] == mode and "error" not in r]
        if not rows:
            continue
        lines.append(
            f"| {mode} | {len(rows)} | {_mean(rows, 'faith_before')} | {_mean(rows, 'faith_after')} | "
            f"{_mean(rows, 'kept_ratio')} | {_mean(rows, 'seconds')} | {_mean(rows, 'tokens')} |"
        )
    failed = [r for r in results if "error" in r]
    if failed:
        lines += ["", f"{len(failed)} run(s) failed:"] + [f"- {r['mode']} / {r['topic']}: {r['error'][:120]}" for r in failed]
    lines += ["", "## Per question", "", "| Topic | Mode | Before | After | Kept | Removed | Rewritten | s |", "|---|---|---|---|---|---|---|---|"]
    for r in results:
        if "error" in r:
            continue
        lines.append(
            f"| {r['topic'][:48]} | {r['mode']} | {r['faith_before']} | {r['faith_after']} | {r['kept_ratio']} | "
            f"{r['removed']} | {r['rewritten']} | {r['seconds']} |"
        )
    lines += [
        "",
        (
            "Notes: faithfulness is judged by an LLM against retrieved passages, not by humans. The writer and "
            "judge may be the same model family, so treat absolute scores as optimistic and compare modes "
            "against each other."
        ),
    ]
    return "\n".join(lines)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3, help="how many questions to run")
    ap.add_argument("--start", type=int, default=0, help="index of the first question (to resume or retry)")
    ap.add_argument("--modes", nargs="+", default=["single", "multi"], choices=["single", "multi"])
    args = ap.parse_args()

    db.init()
    topics = json.loads((HERE / "questions.json").read_text())[args.start : args.start + args.n]
    results: list[dict] = []
    for topic in topics:
        for mode in args.modes:
            print(f"-> {mode:6s} {topic}", flush=True)
            r = await run_one(topic, mode)
            results.append(r)
            print("   ", r.get("error") or f"faith {r['faith_before']} -> {r['faith_after']}, kept {r['kept_ratio']}, {r['seconds']}s", flush=True)
            if "error" in r and "unavailable" in r["error"]:
                print("Providers exhausted; stopping early and saving what we have.")
                break
        else:
            continue
        break

    stamp = time.strftime("%Y%m%d-%H%M%S")
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / f"{stamp}.json").write_text(json.dumps(results, indent=2))
    md = _report(results)
    (HERE / "results" / f"{stamp}.md").write_text(md)
    print("\n" + md)


if __name__ == "__main__":
    asyncio.run(main())
