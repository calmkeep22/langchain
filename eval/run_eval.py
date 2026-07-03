"""Retrieval evaluation harness.

Indexes a codebase (defaults to this repo's app/ folder) and measures
Hit@1, Hit@3, Recall@5, and MRR of the code retriever against
eval/dataset.json. Requires a real embedding API key in .env.

The dataset scores at file granularity, but a chunking strategy that
produces more chunks per file (e.g. AST-based function/method chunking)
can fill up a small raw top-k with several chunks from the same file,
crowding out other files. To score fairly regardless of chunks-per-file,
this pulls a wider raw candidate pool (``--search-k``, default 20) and
only then dedupes down to a per-file ranking before computing Hit@k/MRR.

Usage:
    python eval/run_eval.py [--root PATH] [--label V1] [--k 5] [--search-k 20] [--no-reindex]
"""

import argparse
import json
import sys
import time
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


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * pct))
    return ordered[index]


def get_or_create_project(db, name: str, root_path: str) -> Project:
    try:
        return create_project(db, name, root_path)
    except ServiceError as exc:
        if exc.code != "PROJECT_ALREADY_EXISTS":
            raise
    return db.query(Project).filter(Project.name == name).first()


def evaluate(root: str, label: str, k: int, reindex: bool, search_k: int) -> dict:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    project = get_or_create_project(db, "eval-self-index", root)

    if reindex:
        index_start = time.perf_counter()
        result = index_project_code(db, project.id, force_reindex=True)
        index_latency_ms = round((time.perf_counter() - index_start) * 1000, 1)
        print("indexed:", result, f"({index_latency_ms} ms)")

    embeddings = get_embeddings()
    vector_store = get_code_vector_store(embeddings)

    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    reciprocal_ranks = []
    latencies_ms = []
    rows = []

    for case in dataset:
        search_start = time.perf_counter()
        results = vector_store.similarity_search(case["query"], k=search_k)
        latencies_ms.append((time.perf_counter() - search_start) * 1000)

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
        "avg_latency_ms": round(sum(latencies_ms) / n, 1),
        "p95_latency_ms": round(_percentile(latencies_ms, 0.95), 1),
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
    parser.add_argument("--search-k", type=int, default=20)
    parser.add_argument("--no-reindex", action="store_true")
    args = parser.parse_args()

    evaluate(
        root=args.root,
        label=args.label,
        k=args.k,
        reindex=not args.no_reindex,
        search_k=args.search_k,
    )


if __name__ == "__main__":
    main()
