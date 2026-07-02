"""Retrieval evaluation harness for indexed official docs.

Unlike ``run_eval.py`` (code retrieval), this assumes the target docs have
already been indexed via ``POST /api/index/docs`` (indexing a large site can
take minutes), and only measures retrieval quality against whatever is
currently in the ``official_docs_chunks`` collection.

Usage:
    python eval/run_docs_eval.py [--dataset eval/docs_dataset.json] [--k 5] [--label V1]
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.core.embeddings import get_embeddings  # noqa: E402
from app.core.vector_store import get_docs_vector_store  # noqa: E402

DEFAULT_DATASET_PATH = REPO_ROOT / "eval" / "docs_dataset.json"


def evaluate(dataset_path: Path, k: int, label: str) -> dict:
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))

    embeddings = get_embeddings()
    vector_store = get_docs_vector_store(embeddings)

    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    reciprocal_ranks = []
    rows = []

    for case in dataset:
        results = vector_store.similarity_search(case["query"], k=k)

        ranked_sources = []
        for doc in results:
            source = doc.metadata.get("source")
            if source not in ranked_sources:
                ranked_sources.append(source)

        rank = None
        for position, source in enumerate(ranked_sources, start=1):
            if source == case["expected_source"]:
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
                "expected_source": case["expected_source"],
                "rank": rank,
                "retrieved": ranked_sources,
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
            print(f"       expected={row['expected_source']}")
            print(f"       retrieved={row['retrieved']}")

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--label", default="docs-V1")
    args = parser.parse_args()

    evaluate(dataset_path=Path(args.dataset), k=args.k, label=args.label)


if __name__ == "__main__":
    main()
