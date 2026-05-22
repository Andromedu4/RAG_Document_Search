import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import ProviderCallLog
from app.services.ai_provider import AIProvider, EmbeddingResult, TextGenerationResult
from app.services.costs import estimate_cost_usd


class LoggedAIClient:
    def __init__(self, db: Session, settings: Settings, provider: AIProvider) -> None:
        self.db = db
        self.settings = settings
        self.provider = provider
        self.last_log: ProviderCallLog | None = None

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        return self._with_log(
            operation="embedding",
            model=self.settings.openai_embedding_model,
            call=lambda: self.provider.embed_texts(
                texts,
                model=self.settings.openai_embedding_model,
                dimensions=self.settings.openai_embedding_dimensions,
            ),
        )

    def generate_rag_answer(self, *, instructions: str, input_text: str) -> TextGenerationResult:
        model = self.settings.rag_generation_model
        return self._with_log(
            operation="rag_answer",
            model=model,
            call=lambda: self.provider.generate_text(
                model=model,
                instructions=instructions,
                input_text=input_text,
            ),
        )

    def _with_log(
        self,
        *,
        operation: str,
        model: str,
        call: Callable[[], EmbeddingResult | TextGenerationResult],
    ):
        started = time.perf_counter()
        log = ProviderCallLog(
            provider=self.provider.name,
            operation=operation,
            model=model,
            status="success",
        )
        try:
            result = call()
            latency_ms = int((time.perf_counter() - started) * 1000)
            input_tokens = getattr(result, "input_tokens", 0)
            output_tokens = getattr(result, "output_tokens", 0)
            total_tokens = getattr(result, "total_tokens", input_tokens + output_tokens)
            log.prompt_tokens = input_tokens
            log.completion_tokens = output_tokens
            log.total_tokens = total_tokens
            log.estimated_cost_usd = estimate_cost_usd(
                model, input_tokens=input_tokens, output_tokens=output_tokens
            )
            log.latency_ms = latency_ms
            self.db.add(log)
            self.db.flush()
            self.last_log = log
            return result
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            log.status = "error"
            log.latency_ms = latency_ms
            log.error_message = str(exc)
            self.db.add(log)
            self.db.flush()
            self.last_log = log
            raise
