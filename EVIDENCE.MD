# Evidence

This file collects the main evidence I used to check that the Usage Metering & Billing Engine is working correctly. Most of it comes from pytest, manual API testing, Stripe CLI events, and checking PostgreSQL while I was building the project.

## 1. Idempotent Usage Metering

I tested that using the same idempotency key more than once does not create duplicate usage.

```text
tests/test_metering.py::test_duplicate_idempotency_key_creates_one_event PASSED
tests/test_metering.py::test_duplicate_ai_request_creates_one_event PASSED
```

The database also has a unique constraint on:

```text
(tenant_id, idempotency_key)
```

This gives the application another layer of protection if two requests with the same key happen close together.

## 2. Quota Boundary

I manually put the demo tenant at 999 out of the 1,000 Free-plan API call limit.

```text
Near-quota seed complete
Previous usage: 1
Added events: 998
Current usage: 999
```

The request that moved usage from 999 to exactly 1000 was allowed:

```text
HTTP/1.1 200 OK

{
  "usage_type": "api_call",
  "quantity": 1,
  "cost_microusd": 0,
  "idempotency_key": "quota-boundary-1000"
}
```

The next request tried to go over the limit and was rejected:

```text
HTTP/1.1 429 Too Many Requests

{"detail":"Monthly API call quota exceeded."}
```

I also checked the database and confirmed the rejected request was not stored.

The same boundary behavior is covered by automated tests:

```text
tests/test_metering.py::test_request_at_exact_quota_is_allowed PASSED
tests/test_metering.py::test_request_over_quota_is_rejected PASSED
tests/test_metering.py::test_ai_token_exact_quota_is_allowed PASSED
tests/test_metering.py::test_ai_token_over_quota_is_rejected PASSED
```

## 3. Subscription / Payment State

I temporarily changed the demo tenant subscription to inactive and tried to use the billable endpoint.

```text
HTTP/1.1 402 Payment Required

{"detail":"Subscription is not active."}
```

The same case is covered by:

```text
tests/test_metering.py::test_inactive_subscription_is_rejected PASSED
```

After testing it, I changed the subscription back to active.

## 4. AI Token Metering

AI usage is stored using separate token categories:

```text
input_tokens
cached_input_tokens
output_tokens
reasoning_tokens
```

Relevant test:

```text
tests/test_metering.py::test_ai_token_usage_is_recorded PASSED
```

Example values from that test:

```text
input_tokens         = 300
cached_input_tokens  = 100
output_tokens        = 200
reasoning_tokens     = 50
quantity             = 650
```

I kept these values separate because the categories are not all priced the same.

## 5. Pricing

The pricing constants are stored in:

```text
app/config/pricing.py
```

I use integer micro-USD values instead of floating-point dollar values for the calculations.

The pricing tests cover API calls, regular input, cached input, output, reasoning tokens, mixed usage, zero usage, and negative values.

Example mixed-token calculation:

```text
input_tokens         = 1000
cached_input_tokens  = 200
output_tokens        = 500
reasoning_tokens     = 100

cost_microusd = 1806
```

Relevant tests:

```text
tests/test_pricing.py::test_single_api_call_cost PASSED
tests/test_pricing.py::test_multiple_api_call_cost PASSED
tests/test_pricing.py::test_ai_pricing_with_all_token_categories PASSED
tests/test_pricing.py::test_cached_input_is_cheaper_than_regular_input PASSED
tests/test_pricing.py::test_reasoning_tokens_use_output_price PASSED
tests/test_pricing.py::test_zero_ai_usage_costs_zero PASSED
tests/test_pricing.py::test_negative_token_count_is_rejected PASSED
tests/test_pricing.py::test_negative_api_quantity_is_rejected PASSED
```

## 6. Monthly Usage Rollup

`GET /usage` returns the authenticated tenant's current plan, subscription status, API usage, AI token usage, limits, and total monthly cost.

The rollup test creates:

```text
2 API calls = 200 microUSD

AI usage:
300 input
100 cached input
200 output
50 reasoning

AI cost = 718 microUSD

Expected total = 918 microUSD
```

The endpoint returns the same total.

```text
tests/test_usage.py::test_usage_summary_rolls_up_usage_and_cost PASSED
```

## 7. Tenant Isolation

I tested that one tenant cannot see another tenant's usage.

The test creates two tenants and gives both of them usage. When Tenant A calls `GET /usage`, only Tenant A's usage is returned.

```text
tests/test_usage.py::test_usage_summary_is_tenant_isolated PASSED
tests/test_usage.py::test_usage_requires_api_key PASSED
```

## 8. Stripe Checkout

I tested Stripe Checkout using Stripe test mode.

The application creates a Checkout Session through:

```text
POST /billing/checkout
```

After I completed a test Checkout, Stripe sent:

```text
checkout.session.completed
```

to the local webhook endpoint and the webhook returned `200`.

Afterward, I checked PostgreSQL and confirmed that the demo tenant was on the Pro plan, the subscription was active, and Stripe customer/subscription IDs had been saved.

This confirmed that the plan change was happening through the webhook flow instead of directly from the Checkout endpoint.

## 9. Webhook Signature Verification

I manually sent a forged webhook using:

```text
Stripe-Signature: fake-signature
```

The response was:

```text
HTTP/1.1 400 Bad Request

{"detail":"Invalid Stripe webhook signature."}
```

The event was rejected instead of being processed.

## 10. Stripe Webhook Processing

I used the Stripe CLI while testing the webhook locally.

The application successfully received the event types I needed for the project:

```text
checkout.session.completed
customer.subscription.updated
customer.subscription.deleted
```

Valid Stripe webhook requests returned `200`, and processed event IDs were stored in the `stripe_events` table.

## 11. Stripe Subscription Synchronization

I tested the main subscription changes through Stripe.

A completed Checkout changed the demo tenant from:

```text
Free -> Pro
```

The Stripe customer ID and subscription ID were saved locally.

A later `customer.subscription.updated` event kept the local subscription synchronized as Pro and active.

After canceling the Stripe subscription, the application processed:

```text
customer.subscription.deleted
```

and the local tenant changed back to:

```text
free | active
```

The Stripe customer ID was kept while the old subscription ID was cleared.

## 12. Duplicate Stripe Events

Processed Stripe event IDs are stored in the `stripe_events` table, where the Stripe event ID is the primary key.

Before processing an event, the webhook checks whether the event ID has already been stored. If it has, the handler returns:

```text
status = duplicate
```

The database primary key also prevents the same Stripe event ID from being inserted twice.

## 13. Database and Migrations

I use Alembic to manage the PostgreSQL schema.

The initial migration creates:

```text
tenants
plans
subscriptions
usage_events
stripe_events
```

Some of the important database protections are:

```text
usage_events primary key
stripe_events primary key
unique tenant/idempotency-key constraint
tenant/created-at usage index
foreign keys between tenant, plan, subscription, and usage records
```

Migration command:

```text
alembic upgrade head
```

## 14. Background Job

The usage reconciliation job runs outside the FastAPI request path:

```text
python -m scripts.run_recon
```

It goes through tenants and reports monthly API usage, AI token usage, and cost.

The job retries up to three times if it fails.

```text
tests/test_urecon.py::test_reconciliation_retries_then_succeeds PASSED
```

The test makes the first two attempts fail on purpose and checks that the third succeeds. The sleep call is replaced during the test so it does not actually wait between retries.

## 15. Full Automated Test Suite

I ran the full test suite with:

```text
python -m pytest -v
```

Final output:

```text
=================== test session starts ====================
platform win32 -- Python 3.13.12, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\Uday\FlyRankAi\capstone-metering-billing\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Uday\FlyRankAi\capstone-metering-billing
plugins: anyio-4.14.2
collected 20 items

tests/test_metering.py::test_duplicate_idempotency_key_creates_one_event PASSED [  5%]
tests/test_metering.py::test_request_at_exact_quota_is_allowed PASSED [ 10%]
tests/test_metering.py::test_request_over_quota_is_rejected PASSED [ 15%]
tests/test_metering.py::test_inactive_subscription_is_rejected PASSED [ 20%]
tests/test_metering.py::test_ai_token_usage_is_recorded PASSED [ 25%]
tests/test_metering.py::test_duplicate_ai_request_creates_one_event PASSED [ 30%]
tests/test_metering.py::test_ai_token_exact_quota_is_allowed PASSED [ 35%]
tests/test_metering.py::test_ai_token_over_quota_is_rejected PASSED [ 40%]
tests/test_pricing.py::test_single_api_call_cost PASSED [ 45%]
tests/test_pricing.py::test_multiple_api_call_cost PASSED [ 50%]
tests/test_pricing.py::test_ai_pricing_with_all_token_categories PASSED [ 55%]
tests/test_pricing.py::test_cached_input_is_cheaper_than_regular_input PASSED [ 60%]
tests/test_pricing.py::test_reasoning_tokens_use_output_price PASSED [ 65%]
tests/test_pricing.py::test_zero_ai_usage_costs_zero PASSED [ 70%]
tests/test_pricing.py::test_negative_token_count_is_rejected PASSED [ 75%]
tests/test_pricing.py::test_negative_api_quantity_is_rejected PASSED [ 80%]
tests/test_urecon.py::test_reconciliation_retries_then_succeeds PASSED [ 85%]
tests/test_usage.py::test_usage_summary_rolls_up_usage_and_cost PASSED [ 90%]
tests/test_usage.py::test_usage_summary_is_tenant_isolated PASSED [ 95%]
tests/test_usage.py::test_usage_requires_api_key PASSED [100%]

==================== 20 passed in 1.82s ====================
```

## 16. Secret Handling

My real environment values are stored in `.env`, and that file is ignored by Git.

The repository includes `.env.example` with placeholder values so the required environment variables are still documented without exposing my real keys.

My Stripe API key and webhook secret are not committed to the repository.
