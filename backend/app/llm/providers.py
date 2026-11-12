"""Configured language model providers with structured JSON output."""

from functools import lru_cache
from typing import Protocol

from backend.app.core.config import get_settings
from backend.app.embeddings.providers import EmbeddingConfigurationError
from backend.app.llm.schemas import SynthesisOutput


class LanguageModel(Protocol):
    """Generate structured answers from a system rule and user context."""

    def synthesize(self, system_instruction: str, prompt: str) -> SynthesisOutput: ...


class GeminiLanguageModel:
    """Gemini text generation using JSON structured output."""

    def __init__(self, model: str, api_key: str | None) -> None:
        if not api_key:
            raise EmbeddingConfigurationError("Set GOOGLE_API_KEY to use Gemini answer generation")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise EmbeddingConfigurationError("Install google-genai to use Gemini answer generation") from exc
        self.model = model
        self._types = types
        self._client = genai.Client(api_key=api_key)

    def synthesize(self, system_instruction: str, prompt: str) -> SynthesisOutput:
        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=self._types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=SynthesisOutput,
                max_output_tokens=3000,
            ),
        )
        if response.parsed is not None:
            return SynthesisOutput.model_validate(response.parsed)
        if not response.text:
            raise RuntimeError("Gemini returned no answer text")
        return SynthesisOutput.model_validate_json(response.text)


class OpenAILanguageModel:
    """OpenAI Chat Completions adapter with JSON response validation."""

    def __init__(self, model: str, api_key: str | None) -> None:
        if not api_key:
            raise EmbeddingConfigurationError("Set OPENAI_API_KEY to use OpenAI answer generation")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise EmbeddingConfigurationError("Install openai to use OpenAI answer generation") from exc
        self.model = model
        self._client = OpenAI(api_key=api_key)

    def synthesize(self, system_instruction: str, prompt: str) -> SynthesisOutput:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system_instruction},
                      {"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("OpenAI returned no answer text")
        return SynthesisOutput.model_validate_json(content)


@lru_cache(maxsize=1)
def get_language_model() -> LanguageModel:
    settings = get_settings()
    provider = settings.llm_provider.lower()
    if provider == "gemini":
        return GeminiLanguageModel(settings.llm_model, settings.google_api_key)
    if provider == "openai":
        return OpenAILanguageModel(settings.llm_model, settings.openai_api_key)
    raise EmbeddingConfigurationError(f"Unknown language model provider: {provider}")
