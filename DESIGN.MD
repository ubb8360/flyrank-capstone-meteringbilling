# Usage Metering & Billing Engine — Design

## Problem Statement

SaaS applications need a way to track how much each customer uses, check if they are still within their plan limits, and calculate how much that usage costs.

This gets more complicated when requests are retried or the same event gets sent more than once. If those cases are not handled correctly, usage could accidentally be counted twice or a customer's subscription could be updated incorrectly.

For this capstone, I am building a multi-tenant usage metering and billing service that will:

- Record API and AI-token usage
- Prevent duplicate usage events using idempotency
- Enforce Free and Pro plan quotas
- Calculate usage costs using set pricing rules
- Use Stripe test mode to keep subscription information in sync

The main focus is making the billing logic correct and predictable, especially when requests are retried or customers are close to their usage limits. This is not meant to be a full production billing system.

## Core Success Criteria

The main things I want the system to be able to do are:

1. A retried billable request should only create one usage event.
2. Requests that would go over a tenant's quota should be rejected with a clear response.
3. A request that brings a tenant exactly to its quota should still be allowed.
4. Usage and cost calculations should give consistent results and be covered by tests.
5. Stripe subscription updates should only be accepted from verified webhook events.
6. Sending the same Stripe webhook more than once should not apply the update multiple times.

---

## Data Model

The application will use PostgreSQL with a small relational database.

I want to keep the database fairly simple while still separating each customer's data and keeping enough information to understand where usage totals came from.

The main tables will be `tenants`, `plans`, `subscriptions`, `usage_events`, and `stripe_events`.

### `tenants`

Represents a customer or organization using the service.

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | UUID | Primary identifier |
| `name` | VARCHAR | Tenant name |
| `created_at` | TIMESTAMP | When the tenant was created |

Each usage event and subscription will belong to a tenant.

Using tenants also gives the project a basic multi-tenant setup instead of treating every customer as part of the same account.

---

### `plans`

Stores the subscription plans and their monthly limits.

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | INTEGER | Primary identifier |
| `name` | VARCHAR | Plan name |
| `api_call_limit` | INTEGER | Monthly API call limit |
| `ai_token_limit` | INTEGER | Monthly AI token limit |

For now, the project will have two plans:

| Plan | API Calls / Month | AI Tokens / Month |
| --- | ---: | ---: |
| Free | 1,000 | 100,000 |
| Pro | 10,000 | 1,000,000 |

The Free limits come from the capstone requirements.

The capstone only says that Pro should have higher limits, so I chose 10,000 API calls and 1,000,000 AI tokens. These numbers are mostly there so I have a second plan that is easy to test and demonstrate.

I may move these values into configuration later instead of depending completely on values stored in the database.

---

### `subscriptions`

Stores the current subscription information for each tenant.

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | UUID | Primary identifier |
| `tenant_id` | UUID | Tenant that owns the subscription |
| `plan_id` | INTEGER | Tenant's current plan |
| `status` | VARCHAR | Current subscription status |
| `stripe_customer_id` | VARCHAR, nullable | Stripe customer ID |
| `stripe_subscription_id` | VARCHAR, nullable | Stripe subscription ID |
| `current_period_start` | TIMESTAMP, nullable | Start of the current subscription period |
| `current_period_end` | TIMESTAMP, nullable | End of the current subscription period |
| `updated_at` | TIMESTAMP | Last subscription update |

For this project, each tenant will only have one active subscription record.

The Stripe fields can be empty for tenants that have not gone through Stripe Checkout yet.

Once Stripe is added later in the project, Stripe will be treated as the source of truth for the paid subscription state instead of allowing the client to directly change its own plan.

This is kept simple for the capstone. I am not trying to keep a complete history of every subscription change.

---

### `usage_events`

Stores individual billable actions.

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | UUID | Primary identifier |
| `tenant_id` | UUID | Tenant responsible for the usage |
| `usage_type` | VARCHAR | `api_call` or `ai_tokens` |
| `quantity` | INTEGER | Amount counted toward the quota |
| `input_tokens` | INTEGER, nullable | Standard input tokens |
| `cached_input_tokens` | INTEGER, nullable | Cached input tokens |
| `output_tokens` | INTEGER, nullable | Output tokens |
| `reasoning_tokens` | INTEGER, nullable | Reasoning tokens |
| `cost_microusd` | BIGINT | Calculated cost stored as an integer |
| `idempotency_key` | VARCHAR | Identifies one logical billable request |
| `created_at` | TIMESTAMP | When the event was recorded |

For a normal API call, an event could look like:

```text
usage_type = api_call
quantity = 1
```

The token-specific fields would not be needed for that type of event.

For AI-token usage, the different token categories are stored separately because cached input, regular input, output, and reasoning tokens may not all have the same pricing rules.

I considered only storing one total token count, but keeping the categories separate should make the pricing calculations easier to understand and test later.

The database will also have a unique constraint on:

```text
(tenant_id, idempotency_key)
```

This means the same tenant cannot create two usage events using the same idempotency key.

The application will still check for duplicates in the Python code, but having the database constraint gives another layer of protection if two duplicate requests happen very close together.

Instead of only keeping a running counter like `api_calls_used = 500`, I am storing the individual events. This gives me a record of what actually caused the usage total and should make debugging the metering logic easier.

---

### `stripe_events`

Stores Stripe webhook events that have already been processed.

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | VARCHAR | Stripe event ID |
| `event_type` | VARCHAR | Type of Stripe event |
| `processed_at` | TIMESTAMP | When the event was processed |

Stripe can sometimes send the same webhook more than once, so I need a way to tell if an event was already handled.

When a webhook comes in, the application can check this table for the Stripe event ID.

If the ID is already there, the system will treat it as a duplicate and avoid applying the same subscription change again.

I am using a separate table for this instead of adding Stripe event information to the subscription itself because it keeps webhook deduplication separate from the tenant's actual subscription data.

---

### Relationships

The database relationships should roughly look like this:

```text
plans
  |
  +----< subscriptions >---- tenants
                               |
                               +----< usage_events

stripe_events
  |
  +---- processed Stripe webhook IDs
```

A tenant has a subscription and can have many usage events.

A subscription points to a plan, which determines the tenant's monthly usage limits.

`stripe_events` is mostly separate because its purpose is just to keep track of which webhook events have already been processed.

For now, usage totals will be calculated from the individual `usage_events` instead of keeping another monthly totals table.

A separate totals table could make reads faster in a much larger system, but it would also mean keeping another value synchronized. Since this capstone will have a small amount of test data, calculating the totals from the events is simpler and easier for me to verify.