"""Multi-provider LLM abstraction.

Future-work item: "supporting multiple LLM backends (OpenAI, Anthropic,
open-source models) with a provider abstraction layer, eliminating
single-provider dependency."

Every provider exposes the same two operations - generate() and
generate_stream() - so the agent layer (agents/base.py, services/llm.py)
never has to know which vendor SDK is behind a given response. Gemini
remains the default; OpenAI/Anthropic activate only when LLM_PROVIDER is
set AND the matching API key is present, so an incomplete .env can never
turn a working deployment into a broken one.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator

import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 4096) -> str:
        ...

    @abstractmethod
    def generate_stream(
        self, prompt: str, temperature: float = 0.7, max_tokens: int = 4096
    ) -> AsyncGenerator[str, None]:
        ...


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self):
        self._model = None

    def _get_model(self):
        if self._model is None:
            import google.generativeai as genai

            genai.configure(api_key=settings.GEMINI_API_KEY)
            self._model = genai.GenerativeModel(settings.GEMINI_MODEL)
        return self._model

    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 4096) -> str:
        import google.generativeai as genai

        model = self._get_model()
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=temperature, max_output_tokens=max_tokens
            ),
        )
        return response.text

    async def generate_stream(
        self, prompt: str, temperature: float = 0.7, max_tokens: int = 4096
    ) -> AsyncGenerator[str, None]:
        import google.generativeai as genai

        model = self._get_model()
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=temperature, max_output_tokens=max_tokens
            ),
            stream=True,
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 4096) -> str:
        client = self._get_client()
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    async def generate_stream(
        self, prompt: str, temperature: float = 0.7, max_tokens: int = 4096
    ) -> AsyncGenerator[str, None]:
        client = self._get_client()
        stream = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 4096) -> str:
        client = self._get_client()
        resp = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")

    async def generate_stream(
        self, prompt: str, temperature: float = 0.7, max_tokens: int = 4096
    ) -> AsyncGenerator[str, None]:
        client = self._get_client()
        with client.messages.stream(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text


_provider_cache: dict[str, LLMProvider] = {}


def get_llm_provider() -> LLMProvider:
    """Return the configured provider, falling back to Gemini if unavailable.

    A provider is only usable if its API key is actually set; this keeps a
    half-configured .env (LLM_PROVIDER=openai with no OPENAI_API_KEY) from
    turning every chat request into a 500 instead of just using Gemini.
    """
    choice = (settings.LLM_PROVIDER or "gemini").lower()

    if choice == "openai" and not settings.OPENAI_API_KEY:
        logger.warning("llm_provider_fallback", requested="openai", reason="missing_api_key")
        choice = "gemini"
    elif choice == "anthropic" and not settings.ANTHROPIC_API_KEY:
        logger.warning("llm_provider_fallback", requested="anthropic", reason="missing_api_key")
        choice = "gemini"
    elif choice not in ("gemini", "openai", "anthropic"):
        logger.warning("llm_provider_fallback", requested=choice, reason="unknown_provider")
        choice = "gemini"

    if choice not in _provider_cache:
        _provider_cache[choice] = {
            "gemini": GeminiProvider,
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
        }[choice]()

    return _provider_cache[choice]
