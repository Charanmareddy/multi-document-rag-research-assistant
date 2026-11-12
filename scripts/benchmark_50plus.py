"""Run a real 50+ PDF ingest/index/retrieval latency benchmark through the API."""

import argparse
import json
import math
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx


def percentile(values: list[float], rank: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(rank * len(ordered)) - 1))
    return round(ordered[index], 2)


def api(client: httpx.Client, method: str, url: str, **kwargs):
    response = client.request(method, url, **kwargs)
    response.raise_for_status()
    if response.status_code == 204:
        return None
    return response.json()


def load_queries(path: Path | None) -> list[dict]:
    if path is None:
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(args) -> dict:
    if args.batch_size < 1:
        raise ValueError("batch-size must be at least 1")
    pdfs = sorted(path for path in args.pdf_dir.rglob("*.pdf") if path.is_file())
    if len(pdfs) < 50:
        raise ValueError(f"Provide a representative directory with at least 50 PDFs; found {len(pdfs)}")
    api_base = args.api.rstrip("/") + "/api/v1"
    queries = load_queries(args.queries)
    upload_started = time.perf_counter()
    with httpx.Client(timeout=180.0) as client:
        collection = api(client, "POST", f"{api_base}/collections",
                         json={"name": f"50-plus-benchmark-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"})
        upload_errors = []
        for offset in range(0, len(pdfs), args.batch_size):
            batch = pdfs[offset:offset + args.batch_size]
            files = [("files", (path.name, path.read_bytes(), "application/pdf")) for path in batch]
            result = api(client, "POST", f"{api_base}/documents/upload",
                         data={"collection_id": collection["id"]}, files=files)
            upload_errors.extend(item for item in result["results"] if "error" in item)
        upload_elapsed = time.perf_counter() - upload_started
        uploaded_documents = api(client, "GET", f"{api_base}/documents",
                                 params={"collection_id": collection["id"]})
        if len(uploaded_documents) < 50:
            raise ValueError(f"Only {len(uploaded_documents)} unique readable PDFs were accepted; at least 50 are required")

        index_started = time.perf_counter()
        job = api(client, "POST", f"{api_base}/indexing/start",
                  json={"collection_id": collection["id"]})
        deadline = time.monotonic() + args.timeout_seconds
        while True:
            job = api(client, "GET", f"{api_base}/indexing/status/{job['job_id']}")
            if job["status"] in {"completed", "completed_with_errors", "failed"}:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Indexing job {job['job_id']} did not finish before timeout")
            time.sleep(args.poll_seconds)
        indexing_wall_seconds = time.perf_counter() - index_started

        retrieval_ms = []
        answer_ms = []
        query_results = []
        for item in queries:
            body = {"query": item["query"], "collection_id": collection["id"],
                    "mode": item.get("mode", args.mode), "top_k": item.get("top_k", 10)}
            started = time.perf_counter()
            try:
                search = api(client, "POST", f"{api_base}/research/search", json=body)
            except httpx.HTTPStatusError as exc:
                query_results.append({"query": item["query"], "retrieval_error": exc.response.text})
                continue
            retrieval_ms.append((time.perf_counter() - started) * 1000)
            query_row = {"query": item["query"], "retrieved_count": len(search["results"])}
            if args.run_llm:
                started = time.perf_counter()
                try:
                    answer = api(client, "POST", f"{api_base}/research/query", json=body)
                except httpx.HTTPStatusError as exc:
                    query_row["answer_error"] = exc.response.text
                    query_results.append(query_row)
                    continue
                answer_ms.append((time.perf_counter() - started) * 1000)
                query_row["citation_count"] = len(answer["citations"])
                query_row["reported_timings_ms"] = answer["timings_ms"]
            query_results.append(query_row)

        docs = uploaded_documents
        return {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "collection_id": collection["id"],
            "pdf_count_requested": len(pdfs),
            "documents_uploaded": len(docs),
            "indexed_documents": sum(item["status"] == "indexed" for item in docs),
            "failed_documents": sum(item["status"] == "index_failed" for item in docs),
            "indexed_pages": sum(item["page_count"] or 0 for item in docs if item["status"] == "indexed"),
            "indexed_chunks": sum(item["chunk_count"] for item in docs if item["status"] == "indexed"),
            "upload_seconds": round(upload_elapsed, 2),
            "indexing_wall_seconds": round(indexing_wall_seconds, 2),
            "index_job": {key: job.get(key) for key in ["status", "elapsed_ms", "extraction_ms", "embedding_ms", "vector_store_ms", "error"]},
            "upload_errors": upload_errors,
            "retrieval_latency_ms": {"p50": percentile(retrieval_ms, .5), "p95": percentile(retrieval_ms, .95),
                                     "mean": round(statistics.mean(retrieval_ms), 2) if retrieval_ms else None},
            "answer_latency_ms": {"p50": percentile(answer_ms, .5), "p95": percentile(answer_ms, .95),
                                  "mean": round(statistics.mean(answer_ms), 2) if answer_ms else None},
            "queries": query_results,
            "notes": "Performance observations from this run only; no retrieval or answer-quality score is inferred.",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_dir", type=Path)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--queries", type=Path, help="Optional JSONL file with query strings")
    parser.add_argument("--mode", choices=["bm25", "dense", "hybrid"], default="hybrid")
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--run-llm", action="store_true", help="Also measure answer generation; requires configured LLM")
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/50plus-latest.json"))
    args = parser.parse_args()
    result = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
