"""Configured embedding providers with explicit credential and dependency errors."""

from functools import lru_cache

from backend.app.core.config import get_settings


class EmbeddingConfigurationError(RuntimeError):
    """Raised when a selected embedding backend is not configured or installed."""


class GeminiEmbeddingProvider:
    """Google Gemini embedding adapter using the official Gen AI SDK."""

    def __init__(self, model: str, api_key: str | None) -> None:
        if not api_key:
            raise EmbeddingConfigurationError("Set GOOGLE_API_KEY to use Gemini embeddings")
        try:
            from google import genai
        except ImportError as exc:
            raise EmbeddingConfigurationError("Install google-genai to use Gemini embeddings") from exc
        self.model = model
        self._client = genai.Client(api_key=api_key)

    @property
    def identity(self) -> str:
        return f"gemini:{self.model}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        from google.genai import types
        response = self._client.models.embed_content(
            model=self.model,
            contents=texts,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
        )
        return [list(item.values) for item in (response.embeddings or [])]

    def embed_query(self, text: str) -> list[float]:
        from google.genai import types
        response = self._client.models.embed_content(
            model=self.model,
            contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
        )
        if not response.embeddings:
            raise RuntimeError("Gemini returned no query embedding")
        return list(response.embeddings[0].values)


class OpenAIEmbeddingProvider:
    """OpenAI embedding adapter."""

    def __init__(self, model: str, api_key: str | None) -> None:
        if not api_key:
            raise EmbeddingConfigurationError("Set OPENAI_API_KEY to use OpenAI embeddings")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise EmbeddingConfigurationError("Install openai to use OpenAI embeddings") from exc
        self.model = model
        self._client = OpenAI(api_key=api_key)

    @property
    def identity(self) -> str:
        return f"openai:{self.model}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class LocalEmbeddingProvider:
    """Local Sentence Transformers model loaded only when first used."""

    def __init__(self, model: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingConfigurationError("Install sentence-transformers for local embeddings") from exc
        self.model_name = model
        self._model = SentenceTransformer(model)

    @property
    def identity(self) -> str:
        return f"sentence-transformers:{self.model_name}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._model.encode([text], normalize_embeddings=True)[0].tolist()


@lru_cache(maxsize=1)
def get_embedding_provider():
    settings = get_settings()
    provider = settings.embedding_provider.lower()
    if provider == "gemini":
        return GeminiEmbeddingProvider(settings.embedding_model, settings.google_api_key)
    if provider == "openai":
        return OpenAIEmbeddingProvider(settings.embedding_model, settings.openai_api_key)
    if provider in {"sentence-transformers", "local"}:
        return LocalEmbeddingProvider(settings.embedding_model)
    raise EmbeddingConfigurationError(f"Unknown embedding provider: {provider}")
