from __future__ import annotations

import argparse
import json
import subprocess
import sys

from sqlalchemy import select

from app.db.models import PromptTemplate
from app.db.session import SessionLocal
from app.services.prompts import activate_prompt


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two prompt template versions on the eval set.")
    parser.add_argument("--prompt-a", required=True, help="Format: name:version")
    parser.add_argument("--prompt-b", required=True, help="Format: name:version")
    parser.add_argument("--dataset", default="data/eval/rag_eval.jsonl")
    args = parser.parse_args()

    result_a = _run_for_prompt(args.prompt_a, args.dataset)
    result_b = _run_for_prompt(args.prompt_b, args.dataset)
    print(json.dumps({"prompt_a": result_a, "prompt_b": result_b}, indent=2))


def _run_for_prompt(prompt_ref: str, dataset: str) -> dict:
    name, version = prompt_ref.split(":", 1)
    with SessionLocal() as db:
        prompt = db.scalar(
            select(PromptTemplate).where(
                PromptTemplate.name == name,
                PromptTemplate.version == version,
            )
        )
        if prompt is None:
            raise SystemExit(f"Prompt not found: {prompt_ref}")
        activate_prompt(db, prompt)
        db.commit()

    completed = subprocess.run(
        [sys.executable, "scripts/run_rag_eval.py", "--dataset", dataset, "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    return {"prompt": prompt_ref, "metrics": payload["metrics"]}


if __name__ == "__main__":
    main()
