"""HTTP client for the FastAPI backend."""

import os
from typing import Any

import httpx

API_BASE_URL = os.getenv("RAG_API_URL", "http://127.0.0.1:8000").rstrip("/")


def request(method: str, path: str, **kwargs: Any) -> Any:
    """Call the backend and return JSON, raising useful API errors."""

    try:
        response = httpx.request(method, f"{API_BASE_URL}/api/v1{path}", timeout=60.0, **kwargs)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        try:
            detail = exc.response.json().get("detail", detail)
        except ValueError:
            pass
        raise RuntimeError(f"API returned {exc.response.status_code}: {detail}") from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Cannot reach the API at {API_BASE_URL}. Start the FastAPI server first.") from exc
    if response.status_code == 204:
        return None
    return response.json()


def get_collections() -> list[dict]:
    return request("GET", "/collections")


def upload_pdfs(collection_id: str, uploads: list[Any]) -> dict:
    files = [("files", (item.name, item.getvalue(), "application/pdf")) for item in uploads]
    return request("POST", "/documents/upload", data={"collection_id": collection_id}, files=files)


def upload_zip(collection_id: str, upload: Any) -> dict:
    return request("POST", "/documents/upload-zip", data={"collection_id": collection_id},
                   files={"file": (upload.name, upload.getvalue(), "application/zip")})
