import asyncio
import time
import uuid

from . import db
from .llm import Usage
from .models import Analysis, Report, RunRequest, Source, VerifyStats


class Run:
    """One research run: owns its event log, approval gate and usage counters."""

    def __init__(self, req: RunRequest):
        self.id = uuid.uuid4().hex[:10]
        self.topic = req.topic
        self.mode = req.mode
        self.require_approval = req.require_approval
        self.usage = Usage()
        self.events: list[dict] = []
        self.cond = asyncio.Condition()
        self.finished = False
        self.paused = 0.0
        self._approval: asyncio.Future | None = None
        self.sources: list[Source] = []
        self.analysis: Analysis | None = None
        self.report: Report | None = None
        self.stats: VerifyStats | None = None

    async def emit(self, type_: str, data: dict) -> None:
        async with self.cond:
            seq = len(self.events)
            ev = {"seq": seq, "type": type_, "data": data, "ts": time.time()}
            self.events.append(ev)
            db.add_event(self.id, seq, type_, data, ev["ts"])
            self.cond.notify_all()

    async def wait_for_approval(self, questions: list[str]) -> list[str]:
        self._approval = asyncio.get_running_loop().create_future()
        db.update_run(self.id, status="awaiting_approval")
        await self.emit("awaiting_approval", {"questions": questions})
        waited = time.time()
        approved = await asyncio.wait_for(self._approval, timeout=60 * 30)
        self.paused += time.time() - waited  # human think-time is not run time
        await self.emit("approved", {"questions": approved})
        return approved

    def approve(self, questions: list[str]) -> bool:
        if self._approval and not self._approval.done():
            self._approval.set_result(questions)
            return True
        return False

    async def stream(self, start: int = 0):
        """Yield events from `start`, then live ones until the run ends."""
        i = start
        while True:
            async with self.cond:
                await self.cond.wait_for(lambda i=i: i < len(self.events) or self.finished)
                batch = self.events[i:]
                done = self.finished and i + len(batch) >= len(self.events)
            for ev in batch:
                yield ev
            i += len(batch)
            if done:
                return


class RunManager:
    def __init__(self):
        self.runs: dict[str, Run] = {}
        self.tasks: set[asyncio.Task] = set()
        self.sem = asyncio.Semaphore(1)  # one run at a time keeps the laptop cool

    def start(self, req: RunRequest) -> Run:
        run = Run(req)
        self.runs[run.id] = run
        db.create_run(run.id, run.topic, run.mode)
        task = asyncio.create_task(self._drive(run))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return run

    async def _drive(self, run: Run) -> None:
        from .pipeline import execute

        started = time.time()
        try:
            async with self.sem:
                await execute(run)
            seconds = round(time.time() - started - run.paused, 1)
            db.update_run(
                run.id,
                status="done",
                report=run.report.model_dump() if run.report else None,
                sources=[s.model_dump() for s in run.sources],
                analysis=run.analysis.model_dump() if run.analysis else None,
                stats={**(run.stats.model_dump() if run.stats else {}), "faithfulness": run.stats.faithfulness if run.stats else 0},
                usage={**run.usage.as_dict(), "seconds": seconds},
            )
            await run.emit("done", {"usage": {**run.usage.as_dict(), "seconds": seconds}})
        except Exception as e:  # noqa: BLE001 - surface every failure to the UI instead of dying silently
            db.update_run(run.id, status="error")
            await run.emit("error", {"message": str(e) or e.__class__.__name__})
        finally:
            async with run.cond:
                run.finished = True
                run.cond.notify_all()


manager = RunManager()
