"""Non-secret runtime configuration status."""

from fastapi import APIRouter
from importlib.util import find_spec

from backend.app.core.config import get_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def settings_status() -> dict:
    """Expose provider names and credential presence, never credential values."""

    settings = get_settings()
    if settings.llm_provider == "gemini":
        llm_configured = bool(settings.google_api_key)
    elif settings.llm_provider == "openai":
        llm_configured = bool(settings.openai_api_key)
    else:
        llm_configured = False
    if settings.embedding_provider == "gemini":
        embedding_configured = bool(settings.google_api_key)
    elif settings.embedding_provider == "openai":
        embedding_configured = bool(settings.openai_api_key)
    else:
        embedding_configured = bool(find_spec("sentence_transformers"))
    reranker_configured = (
        settings.reranker == "none"
        or (settings.reranker == "local" and bool(find_spec("sentence_transformers")))
        or (settings.reranker == "cohere" and bool(settings.cohere_api_key))
    )
    return {
        "llm": {"provider": settings.llm_provider, "model": settings.llm_model,
                "configured": llm_configured},
        "embeddings": {"provider": settings.embedding_provider, "model": settings.embedding_model,
                       "configured": embedding_configured},
        "vector_store": {"provider": "qdrant", "mode": "server" if settings.qdrant_url else "local"},
        "reranker": {"provider": settings.reranker,
                     "configured": reranker_configured},
    }
