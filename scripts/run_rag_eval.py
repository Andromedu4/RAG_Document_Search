from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.db.models import Base
from app.db.session import SessionLocal, engine
from app.services.ai_logging import LoggedAIClient
from app.services.ai_provider import build_ai_provider
from app.services.prompts import ensure_default_prompts
from app.services.rag import answer_question


@dataclass
class EvalMetrics:
    total: int = 0
    retrieval_hits: int = 0
    citation_passes: int = 0
    unknown_passes: int = 0
    grounded_passes: int = 0

    def as_dict(self) -> dict[str, float | int]:
        present_total = self.total
        return {
            "total": self.total,
            "retrieval_accuracy": _rate(self.retrieval_hits, present_total),
            "citation_rate": _rate(self.citation_passes, present_total),
            "unknown_behavior_rate": _rate(self.unknown_passes, present_total),
            "grounding_proxy_rate": _rate(self.grounded_passes, present_total),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local RAG evaluation dataset.")
    parser.add_argument("--dataset", default="data/eval/rag_eval.jsonl")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    settings = get_settings()
    if settings.is_sqlite:
        Base.metadata.create_all(bind=engine)

    rows = [json.loads(line) for line in Path(args.dataset).read_text().splitlines() if line.strip()]
    metrics = EvalMetrics()
    details: list[dict] = []

    with SessionLocal() as db:
        ensure_default_prompts(db)
        provider = build_ai_provider(settings)
        ai_client = LoggedAIClient(db=db, settings=settings, provider=provider)

        for row in rows:
            question = row["question"]
            embedding = ai_client.embed_texts([question]).embeddings[0]
            result = answer_question(
                db,
                question=question,
                query_embedding=embedding,
                settings=settings,
                ai_client=ai_client,
            )
            db.commit()

            retrieval_hit = _retrieval_hit(row, result.retrieved)
            has_citation = bool(result.citations)
            unknown_ok = (not row["answer_present"]) and "don't know" in result.answer.lower()
            grounded_ok = unknown_ok or has_citation

            metrics.total += 1
            metrics.retrieval_hits += int(retrieval_hit)
            metrics.citation_passes += int(has_citation)
            metrics.unknown_passes += int(unknown_ok)
            metrics.grounded_passes += int(grounded_ok)
            details.append(
                {
                    "id": row["id"],
                    "retrieval_hit": retrieval_hit,
                    "has_citation": has_citation,
                    "unknown_ok": unknown_ok,
                    "answer": result.answer,
                    "retrieved_chunk_ids": [item.chunk_id for item in result.retrieved],
                }
            )

    payload = {"metrics": metrics.as_dict(), "details": details}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("RAG evaluation")
        for key, value in payload["metrics"].items():
            print(f"{key}: {value}")


def _retrieval_hit(row: dict, retrieved: list) -> bool:
    if not row["answer_present"]:
        return True
    expected_refs = set(row.get("expected_chunk_refs") or [])
    if expected_refs and expected_refs.intersection({item.chunk_id for item in retrieved}):
        return True
    labels = [label.lower() for label in row.get("expected_source_labels", [])]
    haystack = " ".join(f"{item.title} {item.source_label} {item.snippet}" for item in retrieved).lower()
    return any(label in haystack for label in labels)


def _rate(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


if __name__ == "__main__":
    main()
