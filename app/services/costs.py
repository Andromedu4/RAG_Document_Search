from decimal import Decimal

MODEL_PRICING_USD_PER_1M: dict[str, tuple[Decimal, Decimal]] = {
    # Current OpenAI standard processing prices verified from official pricing/model pages
    # on 2026-05-21.
    "text-embedding-3-small": (Decimal("0.02"), Decimal("0")),
    "text-embedding-3-large": (Decimal("0.13"), Decimal("0")),
    "gpt-5.4-nano": (Decimal("0.20"), Decimal("1.25")),
    "gpt-5.4-mini": (Decimal("0.75"), Decimal("4.50")),
    "gpt-5.4": (Decimal("2.50"), Decimal("15.00")),
    "gpt-5.5": (Decimal("5.00"), Decimal("30.00")),
    "llama-3.1-8b-instant": (Decimal("0.05"), Decimal("0.08")),
    "llama-3.3-70b-versatile": (Decimal("0.59"), Decimal("0.79")),
    "openai/gpt-oss-20b": (Decimal("0.075"), Decimal("0.30")),
    "openai/gpt-oss-120b": (Decimal("0.15"), Decimal("0.60")),
}


def estimate_cost_usd(model: str, *, input_tokens: int = 0, output_tokens: int = 0) -> Decimal:
    input_rate, output_rate = MODEL_PRICING_USD_PER_1M.get(model, (Decimal("0"), Decimal("0")))
    cost = (Decimal(input_tokens) / Decimal(1_000_000) * input_rate) + (
        Decimal(output_tokens) / Decimal(1_000_000) * output_rate
    )
    return cost.quantize(Decimal("0.00000001"))
