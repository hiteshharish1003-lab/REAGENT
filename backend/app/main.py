import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from . import db, rag
from .config import settings
from .models import AnswerRequest, ApprovalRequest, RetrieveRequest, RunRequest
from .runs import manager


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    db.fail_interrupted()
    yield


app = FastAPI(title="Verifiable Research Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "mock_llm": settings.mock_llm,
        "mock_search": settings.mock_search,
        "provider": settings.provider or None,
        "fallbacks": settings.compat_providers,
        "model": settings.writer_model or None,
    }


@app.post("/api/runs")
async def create_run(req: RunRequest):
    run = manager.start(req)
    return {"id": run.id}


@app.get("/api/runs")
def list_runs():
    return db.list_runs()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return run


@app.delete("/api/runs/{run_id}")
def delete_run(run_id: str):
    db.delete_run(run_id)
    manager.runs.pop(run_id, None)
    return {"ok": True}


@app.post("/api/runs/{run_id}/approve")
def approve(run_id: str, body: ApprovalRequest):
    run = manager.runs.get(run_id)
    if not run or not run.approve(body.questions):
        raise HTTPException(409, "run is not waiting for approval")
    return {"ok": True}


@app.get("/api/runs/{run_id}/events")
async def events(run_id: str):
    """SSE stream. Live runs stream from memory; finished runs replay from SQLite."""
    run = manager.runs.get(run_id)
    if run:
        async def live():
            async for ev in run.stream():
                yield {"event": ev["type"], "data": json.dumps(ev)}

        return EventSourceResponse(live())

    saved = db.get_run(run_id)
    if not saved:
        raise HTTPException(404, "run not found")

    async def replay():
        for ev in saved["events"]:
            yield {"event": ev["type"], "data": json.dumps(ev)}

    return EventSourceResponse(replay())


# ---- Document engine ----

answer_lock = asyncio.Semaphore(1)  # one model call chain at a time keeps the laptop cool and quotas predictable


@app.get("/api/docs")
def list_docs():
    return rag.list_documents()


@app.post("/api/docs")
async def upload_doc(request: Request, name: str):
    """Raw-body upload (no multipart dependency): the file bytes are the request body, `name` is its filename."""
    data = await request.body()
    if len(data) > rag.MAX_BYTES:
        raise HTTPException(413, "File is larger than 20 MB.")
    try:
        return await asyncio.to_thread(rag.ingest, name, data)
    except rag.IngestError as e:
        raise HTTPException(422, str(e)) from e


@app.delete("/api/docs/{doc_id}")
def delete_doc(doc_id: int):
    rag.delete_document(doc_id)
    return {"ok": True}


@app.post("/api/docs/retrieve")
def retrieve(req: RetrieveRequest):
    return {"passages": rag.retrieve(req.question, req.doc_ids)}


@app.post("/api/docs/answer")
async def answer(req: AnswerRequest):
    try:
        async with answer_lock:
            return await rag.answer(req.question, req.passage_ids, req.verify)
    except rag.IngestError as e:
        raise HTTPException(410, str(e)) from e
    except Exception as e:
        raise HTTPException(502, str(e) or e.__class__.__name__) from e


@app.get("/api/docs/history")
def doc_history():
    return rag.history()


@app.get("/api/docs/history/{qa_id}")
def doc_history_item(qa_id: int):
    item = rag.get_qa(qa_id)
    if not item:
        raise HTTPException(404, "not found")
    return item


@app.delete("/api/docs/history/{qa_id}")
def doc_history_delete(qa_id: int):
    rag.delete_qa(qa_id)
    return {"ok": True}
