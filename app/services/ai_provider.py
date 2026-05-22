from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings
from app.services.text import estimate_tokens, stable_hash


@dataclass(frozen=True)
class EmbeddingResult:
    embeddings: list[list[float]]
    model: str
    input_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class TextGenerationResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int


class AIProvider(Protocol):
    name: str

    def embed_texts(self, texts: list[str], *, model: str, dimensions: int) -> EmbeddingResult:
        raise NotImplementedError

    def generate_text(self, *, model: str, instructions: str, input_text: str) -> TextGenerationResult:
        raise NotImplementedError


class MockAIProvider:
    name = "mock"

    def embed_texts(self, texts: list[str], *, model: str, dimensions: int) -> EmbeddingResult:
        embeddings = [_bag_of_words_embedding(text, dimensions) for text in texts]
        input_tokens = sum(estimate_tokens(text) for text in texts)
        return EmbeddingResult(
            embeddings=embeddings,
            model=model,
            input_tokens=input_tokens,
            total_tokens=input_tokens,
        )

    def generate_text(self, *, model: str, instructions: str, input_text: str) -> TextGenerationResult:
        input_tokens = estimate_tokens(instructions) + estimate_tokens(input_text)
        if "no_answer_expected" in input_text.lower() or "not present" in input_text.lower():
            text = "I don't know based on the provided context."
        else:
            first_source = "[S1]" if "[S1]" in input_text else ""
            text = (
                "Based on the retrieved context, the answer is grounded in the knowledge base. "
                f"{first_source}"
            ).strip()
        output_tokens = estimate_tokens(text)
        return TextGenerationResult(
            text=text,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        )


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str) -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)

    def embed_texts(self, texts: list[str], *, model: str, dimensions: int) -> EmbeddingResult:
        response = self.client.embeddings.create(model=model, input=texts, dimensions=dimensions)
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", None) or getattr(usage, "total_tokens", None)
        input_tokens = input_tokens or sum(estimate_tokens(text) for text in texts)
        embeddings = [item.embedding for item in response.data]
        return EmbeddingResult(
            embeddings=embeddings,
            model=model,
            input_tokens=input_tokens,
            total_tokens=getattr(usage, "total_tokens", input_tokens) if usage else input_tokens,
        )

    def generate_text(self, *, model: str, instructions: str, input_text: str) -> TextGenerationResult:
        response = self.client.responses.create(
            model=model,
            instructions=instructions,
            input=input_text,
        )
        text = response.output_text
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
        output_tokens = getattr(usage, "output_tokens", 0) if usage else 0
        if not input_tokens:
            input_tokens = estimate_tokens(instructions) + estimate_tokens(input_text)
        if not output_tokens:
            output_tokens = estimate_tokens(text)
        return TextGenerationResult(
            text=text,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=getattr(usage, "total_tokens", input_tokens + output_tokens)
            if usage
            else input_tokens + output_tokens,
        )


class GroqProvider:
    name = "groq"

    def __init__(self, api_key: str, base_url: str) -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.embedding_provider = MockAIProvider()

    def embed_texts(self, texts: list[str], *, model: str, dimensions: int) -> EmbeddingResult:
        # Groq supports OpenAI-compatible chat completions. For Groq-only testing,
        # retrieval uses deterministic local embeddings so the app works with one key.
        return self.embedding_provider.embed_texts(texts, model=model, dimensions=dimensions)

    def generate_text(self, *, model: str, instructions: str, input_text: str) -> TextGenerationResult:
        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": input_text},
            ],
            temperature=0,
        )
        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        if not input_tokens:
            input_tokens = estimate_tokens(instructions) + estimate_tokens(input_text)
        if not output_tokens:
            output_tokens = estimate_tokens(text)
        return TextGenerationResult(
            text=text,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=getattr(usage, "total_tokens", input_tokens + output_tokens)
            if usage
            else input_tokens + output_tokens,
        )


def build_ai_provider(settings: Settings) -> AIProvider:
    if settings.use_mock_provider:
        return MockAIProvider()
    if settings.ai_provider == "groq":
        if not settings.groq_api_key:
            return MockAIProvider()
        return GroqProvider(api_key=settings.groq_api_key, base_url=settings.groq_base_url)
    if settings.ai_provider == "openai" and not settings.openai_api_key:
        return MockAIProvider()
    return OpenAIProvider(api_key=settings.openai_api_key or "")


def _bag_of_words_embedding(text: str, dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    tokens = [token for token in _tokenize(text) if token]
    if not tokens:
        return vector
    for token in tokens:
        digest = stable_hash(token)
        index = int(digest[:8], 16) % dimensions
        vector[index] += 1.0
    norm = sum(value * value for value in vector) ** 0.5
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _tokenize(text: str) -> list[str]:
    import re

    return re.findall(r"[a-z0-9]+", text.lower())
