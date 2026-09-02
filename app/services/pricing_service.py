from app.config.pricing import (
    API_CALL_PRICE_MICROUSD,
    CACHED_INPUT_PRICE_MICROUSD_PER_MILLION,
    INPUT_PRICE_MICROUSD_PER_MILLION,
    OUTPUT_PRICE_MICROUSD_PER_MILLION,
    TOKENS_PER_PRICE_UNIT,
)


def calculate_api_call_cost_microusd(
    quantity: int = 1,
) -> int:
    if quantity < 0:
        raise ValueError("API call quantity cannot be negative.")

    return quantity * API_CALL_PRICE_MICROUSD


def calculate_ai_cost_microusd(
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    reasoning_tokens: int,
) -> int:
    token_values = (
        input_tokens,
        cached_input_tokens,
        output_tokens,
        reasoning_tokens,
    )

    if any(value < 0 for value in token_values):
        raise ValueError("Token counts cannot be negative.")

    # Reasoning/thinking tokens use the output-token rate.
    billable_output_tokens = (
        output_tokens + reasoning_tokens
    )

    # Keep entirely in integers.
    cost_numerator = (
        input_tokens
        * INPUT_PRICE_MICROUSD_PER_MILLION
        + cached_input_tokens
        * CACHED_INPUT_PRICE_MICROUSD_PER_MILLION
        + billable_output_tokens
        * OUTPUT_PRICE_MICROUSD_PER_MILLION
    )

    # Round to the nearest micro-USD without floats.
    return (
        cost_numerator + TOKENS_PER_PRICE_UNIT // 2
    ) // TOKENS_PER_PRICE_UNIT