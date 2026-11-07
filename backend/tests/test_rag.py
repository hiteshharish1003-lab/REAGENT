import asyncio

import pytest

from app import db, rag
from app.config import settings


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """A throwaway database, and demo mode so no test ever spends API quota."""
    monkeypatch.setattr(settings, "db_path", tmp_path / "t.db")
    for key in ("anthropic_api_key", "gemini_api_key", "groq_api_key"):
        monkeypatch.setattr(settings, key, "")
    db.init()


DOC = (
    "Solid-state batteries replace the liquid electrolyte with a solid one. This improves safety because solid "
    "electrolytes do not leak or ignite. Energy density can reach 400 Wh/kg in lab cells. Manufacturing remains "
    "expensive, and dendrite growth is a persistent problem. "
) * 12


def test_chunks_are_bounded_and_overlap():
    chunks = rag.chunk_text(DOC)
    assert len(chunks) > 1
    assert all(len(c) <= rag.CHUNK_CHARS * 1.6 for c in chunks)
    # the last sentence of one chunk is carried into the next so facts spanning a boundary stay findable
    assert chunks[0].split(". ")[-1][:20] in chunks[1]


def test_unpunctuated_text_is_still_split():
    assert len(rag.chunk_text("word " * 2000)) > 1


def test_ingest_dedupes_and_rejects(store):
    first = rag.ingest("a.txt", DOC.encode())
    assert not first["duplicate"] and first["chunks"] > 1
    assert rag.ingest("copy.txt", DOC.encode())["duplicate"]
    assert len(rag.list_documents()) == 1
    with pytest.raises(rag.IngestError):
        rag.ingest("x.exe", b"abc")
    with pytest.raises(rag.IngestError):
        rag.ingest("empty.txt", b"   ")


def test_retrieve_scopes_and_ranks(store):
    a = rag.ingest("a.txt", DOC.encode())
    b = rag.ingest("b.txt", b"Quarterly revenue grew twelve percent. Marketing spend fell during the same quarter.")
    hits = rag.retrieve("energy density of the batteries")
    assert hits and hits[0]["doc_id"] == a["id"] and hits[0]["relevance"] == 1.0
    assert rag.retrieve("quarterly revenue", [a["id"]]) == []  # b is out of scope
    assert rag.retrieve("quarterly revenue", [b["id"]])
    assert rag.retrieve("the of and") == []  # only stop words


def test_delete_removes_search_hits(store):
    doc = rag.ingest("a.txt", DOC.encode())
    rag.delete_document(doc["id"])
    assert rag.retrieve("energy density") == [] and rag.list_documents() == []


def test_answer_is_grounded_and_saved(store):
    rag.ingest("a.txt", DOC.encode())
    ids = [h["id"] for h in rag.retrieve("energy density")[:2]]
    out = asyncio.run(rag.answer("energy density?", ids, True))
    sentences = out["report"]["sections"][0]["sentences"]
    assert sentences and all(s["source_ids"] for s in sentences)
    assert out["stats"]["total"] == len(sentences)
    assert rag.get_qa(out["id"])["question"] == "energy density?"
    rag.delete_qa(out["id"])
    assert rag.get_qa(out["id"]) is None


def test_answer_on_deleted_passages_fails_cleanly(store):
    with pytest.raises(rag.IngestError):
        asyncio.run(rag.answer("anything", [999], False))


@pytest.mark.parametrize(
    ("question", "terms", "words", "sentences", "bullets"),
    [
        ("explain solid-state batteries in 100 words", ["solid", "state", "batteries"], 100, None, False),
        ("Explain about a certain topic in 100 words", [], 100, None, False),
        ("list the risks as 5 bullet points", ["risks"], None, 5, True),
        ("describe dendrite growth in two sentences", ["dendrite", "growth"], None, 2, False),
        ("what is the energy density?", ["energy", "density"], None, None, False),
    ],
)
def test_brief_separates_topic_from_instructions(question, terms, words, sentences, bullets):
    b = rag.parse_brief(question)
    assert rag._topic_terms(question) == terms
    assert (b.words, b.sentences, b.bullets) == (words, sentences, bullets)


def test_overview_requests_without_topic_still_retrieve(store):
    rag.ingest("a.txt", DOC.encode())
    assert rag.retrieve("summarise this in 100 words")  # no topic words, so the opening passages are used
    assert rag.retrieve("the of") == []  # a pinpoint question with no usable words does not fall back to an overview


def test_broad_requests_retrieve_more_passages(store):
    rag.ingest("a.txt", ("Batteries store energy. " * 700).encode())
    assert len(rag.retrieve("batteries")) <= 6
    assert len(rag.retrieve("explain batteries in 250 words")) > 6


def test_answer_reports_length_and_format(store):
    rag.ingest("a.txt", DOC.encode())
    ids = [h["id"] for h in rag.retrieve("energy density")[:2]]
    out = asyncio.run(rag.answer("list energy density facts as 3 bullet points", ids, False))
    assert out["bullets"] is True and out["words"] > 0 and out["target_words"] is None
