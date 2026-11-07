from typing import Literal

from pydantic import BaseModel, Field

Verdict = Literal["supported", "contradicted", "unsupported"]


class Source(BaseModel):
    id: int
    title: str
    url: str
    domain: str
    content: str
    quality: float = 0.5  # 0..1 heuristic: primary/official domains rank higher
    quality_reason: str = ""


class Finding(BaseModel):
    text: str
    source_ids: list[int]


class ConflictClaim(BaseModel):
    source_id: int
    claim: str


class Conflict(BaseModel):
    topic: str
    claims: list[ConflictClaim]
    explanation: str


class Analysis(BaseModel):
    findings: list[Finding]
    conflicts: list[Conflict] = Field(default_factory=list)


class Sentence(BaseModel):
    id: str = ""  # assigned by the pipeline, not by the model
    text: str
    source_ids: list[int] = Field(default_factory=list)
    verdict: Verdict | None = None
    evidence: str = ""
    evidence_source_id: int | None = None
    original: str = ""  # set when the verifier rewrote or removed this sentence
    action: Literal["kept", "rewritten", "removed"] = "kept"


class Section(BaseModel):
    heading: str
    sentences: list[Sentence]


class Report(BaseModel):
    title: str
    sections: list[Section]


class Plan(BaseModel):
    questions: list[str]


class Verification(BaseModel):
    verdicts: list[dict]  # [{id, verdict, evidence, source_id}]


class Revisions(BaseModel):
    rewrites: list[dict]  # [{id, text}] where text is null to remove the sentence


class VerifyStats(BaseModel):
    total: int = 0  # sentences judged; unchecked ones are not scored
    supported: int = 0
    contradicted: int = 0
    unsupported: int = 0
    unchecked: int = 0

    @property
    def faithfulness(self) -> float:
        return round(self.supported / self.total, 3) if self.total else 0.0


class RunRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    mode: Literal["multi", "single"] = "multi"
    require_approval: bool = True


class ApprovalRequest(BaseModel):
    questions: list[str] = Field(min_length=1, max_length=8)


class AnswerSentence(BaseModel):
    text: str
    source_ids: list[int] = Field(default_factory=list)


class Answer(BaseModel):
    found: bool = True  # False when the passages do not contain the answer
    sentences: list[AnswerSentence]


class RetrieveRequest(BaseModel):
    question: str = Field(min_length=3, max_length=400)
    doc_ids: list[int] = Field(default_factory=list)  # empty = search every document


class AnswerRequest(BaseModel):
    question: str = Field(min_length=3, max_length=400)
    passage_ids: list[int] = Field(min_length=1, max_length=12)
    verify: bool = True
