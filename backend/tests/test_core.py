import json

import pytest

from app import llm, mock
from app.models import Report, Section, Sentence, Source
from app.search import score_domain
from app.verify import (
    _near_duplicate,
    best_passages,
    compute_stats,
    rewrite_is_faithful,
)


def src(i, text):
    return Source(id=i, title="t", url=f"https://x{i}.example", domain=f"x{i}.example", content=text)


def test_best_passages_picks_the_matching_sentence():
    sources = [src(1, "Adoption grew 18% in 2024, reaching 4.2 million units. Skills shortages could slow growth.")]
    top = best_passages("Adoption grew 18% in 2024", sources, k=1)
    assert top[0]["source_id"] == 1 and "18%" in top[0]["text"]


def test_near_duplicate():
    assert _near_duplicate("Adoption grew 18% in 2024, reaching 4.2 million units.", "Adoption in the sector grew 18% in 2024, reaching 4.2 million units.")
    assert not _near_duplicate("Adoption grew 18% in 2024.", "Skills shortages could slow growth.")


@pytest.mark.parametrize(
    "orig,new,verdict,ok",
    [
        ("Costs are 800 dollars and will drop below 200 by 2028.", "Costs are 800 dollars.", "unsupported", True),
        ("Scaling production of ceramic electrolytes remains a hurdle.", "Scaling up production to meet global demand is a major challenge.", "unsupported", False),
        ("Adoption in the sector grew 12% in 2024, according to government reporting.", "Adoption in the sector grew 18% in 2024, reaching 4.2 million units.", "contradicted", True),
        ("Adoption grew 12% in 2024.", "Skills shortages could slow growth.", "contradicted", False),
        ("", "anything here", "unsupported", False),
    ],
)
def test_rewrite_guard(orig, new, verdict, ok):
    assert rewrite_is_faithful(orig, new, verdict) is ok


def test_stats_ignore_removed_sentences():
    sents = [
        Sentence(id="s1", text="a", verdict="supported"),
        Sentence(id="s2", text="b", verdict="unsupported", action="removed"),
        Sentence(id="s3", text="c", verdict="contradicted"),
    ]
    st = compute_stats(Report(title="t", sections=[Section(heading="h", sentences=sents)]))
    assert (st.total, st.supported, st.contradicted, st.unsupported) == (2, 1, 1, 0)
    assert st.faithfulness == 0.5


def test_extract_json_handles_fences_and_prose():
    assert llm._extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm._extract_json('Sure! {"a": {"b": 2}} hope that helps') == {"a": {"b": 2}}
    with pytest.raises(ValueError):
        llm._extract_json("no json here")


def test_domain_scoring():
    assert score_domain("reports.gov.example")[0] > score_domain("medium.com")[0]


def test_mock_corpus_has_a_numeric_conflict():
    text = " ".join(d["content"] for d in mock.CORPUS)
    assert "18%" in text and "12%" in text


def test_usage_cost_is_zero_for_unpriced_models():
    u = llm.Usage()
    u.add("write", "gemini-3.5-flash", 1000, 500)
    assert u.cost_usd == 0.0 and u.calls == 1


def test_chain_never_uses_lite_models_for_verify(monkeypatch):
    monkeypatch.setattr(llm.settings, "gemini_api_key", "x")
    monkeypatch.setattr(llm.settings, "groq_api_key", "x")
    monkeypatch.setattr(llm, "_exhausted", set())
    strong = {m for models in llm.STRONG.values() for m in models}
    assert {m for _, m in llm._chain("verify")} <= strong
    assert llm._chain("plan")[0][1].endswith("lite")


def test_models_are_json_serialisable():
    s = Sentence(id="s1", text="x", source_ids=[1])
    assert json.loads(s.model_dump_json())["action"] == "kept"


# --- regressions found by the real-model eval -------------------------------------------------

import asyncio

from app import verify
from app.models import Revisions, Verification


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("supported", "supported"),
        ("Supported", "supported"),
        ("partially_supported", "unsupported"),
        ("not supported", "unsupported"),
        ("CONTRADICTED", "contradicted"),
        ("unverifiable", "unsupported"),
        ("maybe?", None),
        (None, None),
    ],
)
def test_normalize_verdict(raw, expected):
    assert verify.normalize_verdict(raw) == expected


def test_normalize_source_id():
    assert verify.normalize_source_id("source 3") == 3
    assert verify.normalize_source_id(4) == 4
    assert verify.normalize_source_id(None) is None
    assert verify.normalize_source_id("") is None


def _report(*texts):
    sents = [Sentence(id=f"s{i + 1}", text=t, source_ids=[1]) for i, t in enumerate(texts)]
    return Report(title="t", sections=[Section(heading="h", sentences=sents)])


def test_unreadable_judge_answers_leave_claims_unchecked_not_deleted(monkeypatch):
    async def fake(stage, system, user, schema, usage, **kw):
        # Skips s2 entirely and answers s1 with junk, on every call (including the retry).
        return Verification(verdicts=[{"id": "[S1]", "verdict": "???", "evidence": "", "source_id": None}])

    monkeypatch.setattr(llm, "call_json", fake)
    report = _report("Adoption grew 18% in 2024 overall.", "Costs fell by forty percent last year.")
    asyncio.run(verify.verify_report(report, [src(1, "Adoption grew 18% in 2024 overall.")], llm.Usage(), "x"))
    assert [s.verdict for s in report.sections[0].sentences] == [None, None]
    st = compute_stats(report)
    assert (st.total, st.unchecked) == (0, 2)


def test_judge_wording_and_ids_are_tolerated(monkeypatch):
    async def fake(stage, system, user, schema, usage, **kw):
        return Verification(
            verdicts=[
                {"id": "[S1]", "verdict": "Supported", "evidence": "ev", "source_id": "source 1"},
                {"id": "s2", "verdict": "partially_supported", "evidence": "part", "source_id": 1},
            ]
        )

    monkeypatch.setattr(llm, "call_json", fake)
    report = _report("Adoption grew 18% in 2024 overall.", "Costs fell by forty percent last year.")
    asyncio.run(verify.verify_report(report, [src(1, "x")], llm.Usage(), "x"))
    a, b = report.sections[0].sentences
    assert (a.verdict, a.evidence_source_id) == ("supported", 1)
    assert (b.verdict, b.evidence) == ("unsupported", "part")


def test_revise_refuses_to_gut_the_report(monkeypatch):
    async def fake(stage, system, user, schema, usage, **kw):
        return Revisions(rewrites=[{"id": "s1", "text": None}, {"id": "s2", "text": None}, {"id": "s3", "text": None}])

    monkeypatch.setattr(llm, "call_json", fake)
    report = _report("one claim here is long enough", "two claim here is long enough", "three claim here is long enough")
    for s in report.sections[0].sentences:
        s.verdict = "unsupported"
    applied = asyncio.run(verify.revise_report(report, [src(1, "x")], llm.Usage(), "x"))
    assert applied is False
    assert all(s.action == "kept" for s in report.sections[0].sentences)


def test_source_block_respects_budget():
    from app.pipeline import _source_block

    many = [src(i, "word " * 400) for i in range(1, 21)]  # 20 sources x 2000 chars
    block = _source_block(many, budget=6000)
    assert len(block) < 9000 and "[source 20]" in block  # every source still represented
    assert len(_source_block(many[:2], budget=6000)) > 2500  # few sources keep their full text
