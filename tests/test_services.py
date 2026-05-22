from decimal import Decimal

from app.services.ai_provider import MockAIProvider
from app.services.chunking import chunk_text
from app.services.costs import estimate_cost_usd


def test_chunking_is_stable():
    text = "Paragraph one about retrieval.\n\nParagraph two about embeddings." * 20

    first = chunk_text(text, max_chars=180, overlap_chars=30)
    second = chunk_text(text, max_chars=180, overlap_chars=30)

    assert [chunk.content_hash for chunk in first] == [chunk.content_hash for chunk in second]
    assert len(first) > 1


def test_mock_provider_embeddings_are_query_sensitive():
    provider = MockAIProvider()

    result = provider.embed_texts(
        ["semantic retrieval search", "unrelated finance payroll"],
        model="text-embedding-3-small",
        dimensions=64,
    )

    assert len(result.embeddings) == 2
    assert result.embeddings[0] != result.embeddings[1]
    assert result.input_tokens > 0


def test_cost_estimation_for_rag_call():
    cost = estimate_cost_usd("gpt-5.4-nano", input_tokens=3000, output_tokens=500)

    assert cost == Decimal("0.00122500")
