"""Retrieval evaluation harness.

Indexes a codebase (defaults to this repo's app/ folder) and measures
Hit@1, Hit@3, Recall@5, and MRR of the code retriever against
eval/dataset.json. Requires a real embedding API key in .env.

Usage:
    python eval/run_eval.py [--root PATH] [--label V1] [--k 5] [--no-reindex]
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.core.embeddings import get_embeddings  # noqa: E402
from app.core.errors import ServiceError  # noqa: E402
from app.core.vector_store import get_code_vector_store  # noqa: E402
from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.models import chunk, document, project  # noqa: E402, F401
from app.models.project import Project  # noqa: E402
from app.services.code_indexing_service import index_project_code  # noqa: E402
from app.services.project_service import create_project  # noqa: E402

DATASET_PATH = REPO_ROOT / "eval" / "dataset.json"


def get_or_create_project(db, name: str, root_path: str) -> Project:
    try:
        return create_project(db, name, root_path)
    except ServiceError as exc:
        if exc.code != "PROJECT_ALREADY_EXISTS":
            raise
    return db.query(Project).filter(Project.name == name).first()


def evaluate(root: str, label: str, k: int, reindex: bool) -> dict:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    project = get_or_create_project(db, "eval-self-index", root)

    if reindex:
        result = index_project_code(db, project.id, force_reindex=True)
        print("indexed:", result)

    embeddings = get_embeddings()
    vector_store = get_code_vector_store(embeddings)

    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    reciprocal_ranks = []
    rows = []

    for case in dataset:
        results = vector_store.similarity_search(case["query"], k=k)

        ranked_files = []
        for doc in results:
            file_path = doc.metadata.get("file_path")
            if file_path not in ranked_files:
                ranked_files.append(file_path)

        rank = None
        for position, file_path in enumerate(ranked_files, start=1):
            if file_path == case["expected_file"]:
                rank = position
                break

        reciprocal_ranks.append(1 / rank if rank else 0.0)
        if rank == 1:
            hits_at_1 += 1
        if rank is not None and rank <= 3:
            hits_at_3 += 1
        if rank is not None and rank <= 5:
            hits_at_5 += 1

        rows.append(
            {
                "query": case["query"],
                "expected_file": case["expected_file"],
                "rank": rank,
                "retrieved": ranked_files,
            }
        )

    n = len(dataset)
    metrics = {
        "label": label,
        "n": n,
        "hit@1": round(hits_at_1 / n, 3),
        "hit@3": round(hits_at_3 / n, 3),
        "recall@5": round(hits_at_5 / n, 3),
        "mrr": round(sum(reciprocal_ranks) / n, 3),
    }

    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    for row in rows:
        status = "OK" if row["rank"] else "MISS"
        print(f"[{status}] rank={row['rank']}  Q: {row['query']}")
        if not row["rank"]:
            print(f"       expected={row['expected_file']}  retrieved={row['retrieved']}")

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(REPO_ROOT / "app"))
    parser.add_argument("--label", default="V1")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--no-reindex", action="store_true")
    args = parser.parse_args()

    evaluate(root=args.root, label=args.label, k=args.k, reindex=not args.no_reindex)


if __name__ == "__main__":
    main()
