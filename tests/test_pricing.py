import pytest

from app.services.pricing_service import (
    calculate_ai_cost_microusd,
    calculate_api_call_cost_microusd,
)


def test_single_api_call_cost():
    cost = calculate_api_call_cost_microusd()

    assert cost == 100


def test_multiple_api_call_cost():
    cost = calculate_api_call_cost_microusd(quantity=25)

    assert cost == 2500


def test_ai_pricing_with_all_token_categories():
    cost = calculate_ai_cost_microusd(
        input_tokens=1000,
        cached_input_tokens=200,
        output_tokens=500,
        reasoning_tokens=100,
    )

    assert cost == 1806


def test_cached_input_is_cheaper_than_regular_input():
    regular_input_cost = calculate_ai_cost_microusd(
        input_tokens=1_000_000,
        cached_input_tokens=0,
        output_tokens=0,
        reasoning_tokens=0,
    )

    cached_input_cost = calculate_ai_cost_microusd(
        input_tokens=0,
        cached_input_tokens=1_000_000,
        output_tokens=0,
        reasoning_tokens=0,
    )

    assert regular_input_cost == 300_000
    assert cached_input_cost == 30_000
    assert cached_input_cost < regular_input_cost


def test_reasoning_tokens_use_output_price():
    output_cost = calculate_ai_cost_microusd(
        input_tokens=0,
        cached_input_tokens=0,
        output_tokens=1_000_000,
        reasoning_tokens=0,
    )

    reasoning_cost = calculate_ai_cost_microusd(
        input_tokens=0,
        cached_input_tokens=0,
        output_tokens=0,
        reasoning_tokens=1_000_000,
    )

    assert output_cost == 2_500_000
    assert reasoning_cost == 2_500_000
    assert reasoning_cost == output_cost


def test_zero_ai_usage_costs_zero():
    cost = calculate_ai_cost_microusd(
        input_tokens=0,
        cached_input_tokens=0,
        output_tokens=0,
        reasoning_tokens=0,
    )

    assert cost == 0


def test_negative_token_count_is_rejected():
    with pytest.raises(
        ValueError,
        match="Token counts cannot be negative"
    ):
        calculate_ai_cost_microusd(
            input_tokens=-1,
            cached_input_tokens=0,
            output_tokens=0,
            reasoning_tokens=0,
        )


def test_negative_api_quantity_is_rejected():
    with pytest.raises(
        ValueError,
        match="API call quantity cannot be negative"
    ):
        calculate_api_call_cost_microusd(quantity=-1)