"""Evaluate retrieval quality against a query/chunk relevance JSONL dataset."""

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.database.session import SessionLocal
from backend.app.retrieval.bm25_retriever import bm25_search
from backend.app.retrieval.dense_retriever import dense_search
from backend.app.retrieval.hybrid_retriever import hybrid_search
from backend.app.retrieval.models import SearchFilters


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    return sum(item in relevant for item in retrieved[:k]) / max(k, 1)


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    return sum(item in relevant for item in retrieved[:k]) / max(len(relevant), 1)


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for index, item in enumerate(retrieved, 1):
        if item in relevant:
            return 1.0 / index
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    dcg = sum(1.0 / math.log2(index + 1) for index, item in enumerate(retrieved[:k], 1) if item in relevant)
    ideal = sum(1.0 / math.log2(index + 1) for index in range(1, min(len(relevant), k) + 1))
    return dcg / ideal if ideal else 0.0


def evaluate_dataset(db: Session, dataset: list[dict], collection_id: str,
                     mode: str, top_k: int) -> dict:
    per_query = []
    for row in dataset:
        relevant = set(row.get("relevant_chunk_ids", []))
        if not relevant:
            raise ValueError("Every dataset row must include at least one relevant_chunk_id")
        filters = SearchFilters(collection_id=collection_id, document_ids=row.get("document_ids", []))
        query = row["query"]
        if mode == "bm25":
            found = bm25_search(db, query, filters, top_k)
        elif mode == "dense":
            found = dense_search(query, filters, top_k)
        else:
            found = hybrid_search(db, query, filters, top_k)
        retrieved = [item.chunk_id for item in found]
        per_query.append({
            "query": query,
            "precision_at_k": precision_at_k(retrieved, relevant, top_k),
            "recall_at_k": recall_at_k(retrieved, relevant, top_k),
            "mrr": reciprocal_rank(retrieved, relevant),
            "ndcg_at_k": ndcg_at_k(retrieved, relevant, top_k),
        })
    metric_names = ["precision_at_k", "recall_at_k", "mrr", "ndcg_at_k"]
    averages = {name: sum(row[name] for row in per_query) / max(len(per_query), 1) for name in metric_names}
    return {"collection_id": collection_id, "mode": mode, "top_k": top_k,
            "evaluated_queries": len(per_query), "averages": averages, "per_query": per_query}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--collection-id", required=True)
    parser.add_argument("--mode", choices=["bm25", "dense", "hybrid"], default="hybrid")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/latest.json"))
    args = parser.parse_args()
    dataset = [json.loads(line) for line in args.dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    with SessionLocal() as db:
        report = evaluate_dataset(db, dataset, args.collection_id, args.mode, args.top_k)
    report.update({"dataset": str(args.dataset), "timestamp_utc": datetime.now(timezone.utc).isoformat()})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["averages"], indent=2))


if __name__ == "__main__":
    main()
