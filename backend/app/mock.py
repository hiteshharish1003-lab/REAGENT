"""Deterministic stand-ins for Claude and Tavily so the whole app runs with no API keys.

The mock corpus deliberately contains a numeric conflict between two sources, one report
sentence that misquotes a source, and one claim no source supports. That lets the
verification UI demonstrate all three verdicts offline.
"""

import hashlib
import re

CORPUS = [
    {
        "title": "Annual Sector Outlook 2025",
        "url": "https://reports.gov.example/outlook-2025",
        "content": (
            "Adoption in the sector grew 18% in 2024, reaching 4.2 million units. "
            "Government incentives accounted for roughly a third of new demand. "
            "Regional uptake remains concentrated in five metropolitan areas."
        ),
    },
    {
        "title": "Longitudinal Adoption Study",
        "url": "https://research.edu.example/adoption-study",
        "content": (
            "A longitudinal study found that adoption grew 12% in 2024 when counting only new commercial registrations. "
            "Supply chain constraints delayed deliveries by an average of eleven weeks. "
            "Consumer trust in the technology rose steadily over the period."
        ),
    },
    {
        "title": "Investment Pours Into Local Production",
        "url": "https://news.example/investment-local-production",
        "content": (
            "Analysts expect investment in the sector to reach 9 billion dollars by 2027. "
            "Several manufacturers announced new local production facilities this year. "
            "Infrastructure gaps remain the most cited barrier by buyers."
        ),
    },
    {
        "title": "Why I Think The Market Will Explode",
        "url": "https://medium.com/@someone/market-will-explode",
        "content": (
            "Many experts believe the market will double within three years. "
            "Prices have fallen sharply, making products more accessible. "
            "Early adopters report high satisfaction."
        ),
    },
    {
        "title": "Policy Frameworks and Outcomes",
        "url": "https://oecd.org/policy-frameworks-outcomes",
        "content": (
            "Policy frameworks that pair subsidies with infrastructure targets show stronger outcomes. "
            "Operating costs fall by roughly 40% compared to conventional alternatives. "
            "Skills shortages could slow growth in the medium term."
        ),
    },
]


def search_results(query: str) -> list[dict]:
    start = int(hashlib.sha1(query.encode()).hexdigest(), 16) % len(CORPUS)
    return [CORPUS[(start + i) % len(CORPUS)] for i in range(3)]


def _sid(sources: list[dict], needle: str) -> int | None:
    for s in sources:
        if needle in s["domain"]:
            return s["id"]
    return None


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def respond(stage: str, ctx: dict) -> dict:
    topic = ctx.get("topic", "the topic")
    sources = ctx.get("sources", [])

    if stage == "plan":
        return {
            "questions": [
                f"What is the current state and scale of {topic}?",
                f"What are the main growth drivers and policies shaping {topic}?",
                f"What barriers and risks affect {topic}?",
                f"What do forecasts and investment data say about the future of {topic}?",
            ]
        }

    if stage == "analyze":
        findings = [
            {"text": _sentences(s["content"])[0], "source_ids": [s["id"]]} for s in sources[:5]
        ]
        conflicts = []
        a, b = _sid(sources, "gov.example"), _sid(sources, "edu.example")
        if a is not None and b is not None:
            conflicts.append(
                {
                    "topic": "2024 adoption growth rate",
                    "claims": [
                        {"source_id": a, "claim": "Adoption grew 18% in 2024"},
                        {"source_id": b, "claim": "Adoption grew 12% in 2024"},
                    ],
                    "explanation": "The study counts only new commercial registrations, while the government outlook "
                    "counts all units. The difference is definitional rather than a factual disagreement.",
                }
            )
        return {"findings": findings, "conflicts": conflicts}

    if stage in ("write", "single"):
        gov, edu = _sid(sources, "gov.example"), _sid(sources, "edu.example")
        news, blog = _sid(sources, "news.example"), _sid(sources, "medium.com")
        oecd = _sid(sources, "oecd.org")

        def sent(text, *ids):
            return {"text": text, "source_ids": [i for i in ids if i is not None]}

        return {
            "title": f"{topic}: What the evidence says",
            "sections": [
                {
                    "heading": "Where things stand",
                    "sentences": [
                        sent("Adoption grew 18% in 2024, reaching 4.2 million units.", gov),
                        sent("Government incentives accounted for roughly a third of new demand.", gov),
                        # Deliberate misquote: cites the government report but uses the study's figure.
                        sent("Adoption in the sector grew 12% in 2024, according to government reporting.", gov),
                    ],
                },
                {
                    "heading": "What is driving and limiting growth",
                    "sentences": [
                        sent("Policy frameworks that pair subsidies with infrastructure targets show stronger outcomes.", oecd),
                        sent("Infrastructure gaps remain the most cited barrier by buyers.", news),
                        sent("Supply chain constraints delayed deliveries by an average of eleven weeks.", edu),
                        sent("Skills shortages could slow growth in the medium term.", oecd),
                    ],
                },
                {
                    "heading": "Outlook",
                    "sentences": [
                        sent("Analysts expect investment in the sector to reach 9 billion dollars by 2027.", news),
                        sent("Operating costs fall by roughly 40% compared to conventional alternatives.", oecd),
                        # Deliberate unsupported claim: the cited blog says nothing like this.
                        sent("The sector will fully replace conventional alternatives by 2026.", blog),
                    ],
                },
            ],
        }

    if stage == "ask":
        picked = [_sentences(x["content"])[0] for x in sources[:3] if _sentences(x["content"])]
        return {
            "found": bool(picked),
            "sentences": [{"text": t, "source_ids": [x["id"]]} for t, x in zip(picked, sources)]
            or [{"text": "The documents do not cover this question.", "source_ids": []}],
        }

    if stage == "verify":
        out = []
        for item in ctx.get("items", []):
            claim_nums = set(re.findall(r"\d+(?:\.\d+)?", item["text"]))
            claim_words = set(re.findall(r"[a-z]{4,}", item["text"].lower()))
            best = (0.0, None)
            for p in item["passages"]:
                words = set(re.findall(r"[a-z]{4,}", p["text"].lower()))
                overlap = len(claim_words & words) / max(1, len(claim_words))
                if overlap > best[0]:
                    best = (overlap, p)
            overlap, p = best
            if p is None or overlap < 0.45:
                out.append({"id": item["id"], "verdict": "unsupported", "evidence": "", "source_id": None})
                continue
            passage_nums = set(re.findall(r"\d+(?:\.\d+)?", p["text"]))
            verdict = "contradicted" if claim_nums and not claim_nums <= passage_nums else "supported"
            out.append({"id": item["id"], "verdict": verdict, "evidence": p["text"], "source_id": p["source_id"]})
        return {"verdicts": out}

    if stage == "revise":
        rewrites = []
        for item in ctx.get("items", []):
            if item["verdict"] == "contradicted" and item["evidence"]:
                rewrites.append({"id": item["id"], "text": item["evidence"]})
            else:
                rewrites.append({"id": item["id"], "text": None})
        return {"rewrites": rewrites}

    raise ValueError(f"unknown mock stage {stage}")
