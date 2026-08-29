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
| `api_key_hash` | VARCHAR | Hashed API key used to identify the tenant |

Each usage event and subscription will belong to a tenant.

For the core version of the project, each tenant will also have one API key used to identify it when making requests. Only a hash of the key will be stored in the database instead of storing the original key directly.

Using tenants gives the project a basic multi-tenant setup instead of treating every customer as part of the same account. I am keeping it to one API key per tenant because key rotation and multiple keys per customer are outside the main scope of this project.

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

---

## API Design

I want to keep the API fairly small because the main point of this capstone is the billing logic, not building a large number of endpoints.

For the core project, I plan to have five main endpoints:

- `GET /health`
- `POST /generate`
- `GET /usage`
- `POST /billing/checkout`
- `POST /webhooks/stripe`

The `/generate` endpoint will be the main billable endpoint. It will simulate API and AI usage instead of calling a real AI model.

---

### `GET /health`

Basic health check to make sure the FastAPI application is running.

Example response:

```json
{
  "status": "healthy"
}
```

This endpoint is mostly for setup, Docker testing, and making it easy to tell if the API started correctly.

---

### `POST /generate`

This will be the dummy billable endpoint for the project.

It will simulate an action that would normally cost money in a SaaS application.

Instead of actually generating AI content, the request will provide usage information that the billing system can meter.

A request will also need an idempotency key.

Example header:

```text
Idempotency-Key: generate-demo-001
```

For a basic API call, the request could look like:

```json
{
  "usage_type": "api_call",
  "quantity": 1
}
```

For simulated AI usage:

```json
{
  "usage_type": "ai_tokens",
  "input_tokens": 1000,
  "cached_input_tokens": 200,
  "output_tokens": 500,
  "reasoning_tokens": 100
}
```

The server will validate these values and use them to determine the amount of usage and cost.

I am keeping API-call usage and AI-token usage on the same endpoint because I only need one billable action to demonstrate the metering system.

Later, if this were a larger application, different product endpoints could call the same metering service internally.


### Basic Request Flow

For an accepted request, the endpoint should roughly do the following:

1. Identify the tenant making the request.
2. Validate the request and the `Idempotency-Key`.
3. Check if the idempotency key was already used.
4. Load the tenant's current subscription and plan.
5. Calculate the tenant's current monthly usage.
6. Check whether the new request would go over the quota.
7. Calculate the cost of the request.
8. Store one `usage_event`.
9. Return the result.

I do not plan to put all of this logic directly inside the FastAPI route. The route should mainly validate the HTTP request and call the service layer.

---

## Quota Behavior

The basic quota rule will be:

```text
current usage + requested usage <= plan limit
```

If that is true, the request is allowed.

If the request would make usage go above the plan limit, it will be rejected.

For example, on the Free plan:

```text
Current API calls: 999
Requested: 1

999 + 1 = 1000

Allowed
```

But:

```text
Current API calls: 1000
Requested: 1

1000 + 1 = 1001

Rejected
```

I chose to allow the request that reaches the limit exactly because it makes the boundary easy to explain and test.

A normal usage quota being exceeded will return:

```text
429 Too Many Requests
```

The response should include a useful message instead of only returning the status code.

Example:

```json
{
  "detail": "Monthly API call quota exceeded."
}
```

A `402 Payment Required` response will be used when the issue is related to the subscription or payment state instead of normal usage.

For example, a tenant that needs to upgrade or does not have a valid paid subscription could receive a `402`.

I want to keep the difference simple:

```text
429 = usage limit problem
402 = subscription/payment problem
```

---

### `GET /usage`

Returns the current tenant's usage information for the active billing period.

Example response:

```json
{
  "plan": "free",
  "subscription_status": "active",
  "api_calls": {
    "used": 425,
    "limit": 1000
  },
  "ai_tokens": {
    "used": 42000,
    "limit": 100000
  },
  "cost_microusd": 12500
}
```

The totals will be calculated from the tenant's `usage_events`.

For this capstone, I am okay with calculating the totals when the endpoint is requested instead of keeping another summary table updated.

With the small amount of test data in this project, that should be simple enough and easier to verify.

---

### `POST /billing/checkout`

Creates a Stripe Checkout session in test mode.

The main use for this endpoint will be upgrading a tenant from Free to Pro.

The endpoint should return the Stripe Checkout URL so the test checkout can be completed.

One important part of the design is that calling this endpoint will **not** immediately change the tenant to Pro.

The plan change should only happen after Stripe sends a verified webhook confirming the subscription.

This keeps the application from trusting a client that simply says a payment succeeded.

---

### `POST /webhooks/stripe`

Receives Stripe webhook events.

The main events I expect to support are:

```text
checkout.session.completed
customer.subscription.updated
customer.subscription.deleted
```

The endpoint should:

1. Read the incoming webhook.
2. Verify the Stripe signature.
3. Return `400 Bad Request` if the signature is invalid.
4. Check whether the Stripe event ID has already been processed.
5. Ignore the event if it is a duplicate.
6. Update the tenant's subscription if the event is valid.
7. Store the Stripe event ID after it is handled.

I am only planning to support the Stripe events needed for the capstone instead of trying to handle every event Stripe can send.

---

## Idempotency Strategy

Idempotency is one of the main parts of this project.

Every billable request to `POST /generate` must contain an `Idempotency-Key`.

For example:

```text
Idempotency-Key: generate-demo-001
```

The idea is that one idempotency key represents one logical billable action.

### First Request

The first time the request is received:

```text
generate-demo-001
        |
        v
No existing usage event
        |
        v
Check quota
        |
        v
Calculate cost
        |
        v
Store usage event
        |
        v
Return result
```

### Retried Request

If the client retries the same request:

```text
generate-demo-001
        |
        v
Existing usage event found
        |
        v
Do not create another event
        |
        v
Return the existing result
```

This means a network retry should not cause the customer's usage to increase twice.

The application code will check for an existing event first, but PostgreSQL will also enforce the unique constraint:

```text
(tenant_id, idempotency_key)
```

I am using both because the Python check makes the normal retry behavior easy to handle, while the database constraint protects against a situation where two requests arrive very close together.

For the scope of this project, I am not trying to build a full reusable idempotency framework. I only need it on the billable action where duplicate processing would affect usage.

Stripe webhooks will use a similar idea, but they will be deduplicated using Stripe's own event IDs stored in the `stripe_events` table.

---

## Tenant Identification

Every billable request and usage query needs to be associated with one tenant.

I do not want the client to be able to simply send any `tenant_id` in the request body and access another tenant's information.

For the core version, I plan to use a simple API-key based approach where the request is authenticated and the backend determines which tenant the key belongs to.

The exact authentication implementation will be finalized while building the API.

This is intentionally simpler than a full user login system because authentication is not the main focus of the capstone, but the API still needs a real way to keep tenant data separated.

---

## Architecture

I want to keep the project separated into a few basic layers instead of putting all of the billing logic directly inside the FastAPI routes.

The general flow will be:

```text
Client / Stripe
      |
      v
-------------------------
API Layer
-------------------------
FastAPI routes
Request validation
Status codes / responses
      |
      v
-------------------------
Service Layer
-------------------------
Metering logic
Quota checks
Pricing calculations
Subscription logic
      |
      v
-------------------------
Repository / Data Layer
-------------------------
Database queries
Create/read usage events
Tenant and plan lookups
Subscription updates
      |
      v
-------------------------
PostgreSQL
-------------------------
tenants
plans
subscriptions
usage_events
stripe_events
```

The main idea is:

```text
API -> Services -> Repositories -> Database
```

I have used this type of separation before in smaller backend projects, and I think it makes sense here because the billing rules should not depend directly on FastAPI.

For example, the quota logic should be something I can test without needing to send an actual HTTP request every time.

I do not plan to make every class use interfaces or abstract base classes. That would probably be useful in a much larger project, but for this capstone I mainly want the different responsibilities to stay separated and understandable.

---

### API Layer

The API layer will contain the FastAPI routes.

Its main responsibilities will be:

- Accept incoming requests
- Validate request data
- Read headers such as `Idempotency-Key`
- Authenticate the tenant
- Call the correct service
- Return the correct HTTP response and status code

I want to avoid putting database queries or large amounts of billing logic directly inside the route functions.

A route should mostly handle the HTTP side of the request and then pass the actual work to a service.

---

### Service Layer

The service layer will contain most of the actual billing rules.

I currently expect to have services similar to:

```text
MeterService
QuotaService
PricingService
SubscriptionService
```

`MeterService` will probably handle the main billable request flow.

It will work with the other services to:

1. Check for duplicate requests
2. Load the tenant's plan
3. Check the quota
4. Calculate the cost
5. Record the usage event

`QuotaService` will contain the logic for checking whether new usage is allowed.

`PricingService` will handle API and AI-token cost calculations.

`SubscriptionService` will handle subscription changes caused by Stripe events.

These may change a little once I start implementing the project. I am using them as a starting point instead of trying to design every class before writing any code.

---

### Repository / Data Layer

The repository layer will handle database access.

I expect to have repository code for things such as:

- Tenants
- Plans
- Subscriptions
- Usage events
- Stripe events

For example, instead of having the metering service contain SQL for checking an idempotency key, it could call something similar to:

```text
usage_repository.get_by_idempotency_key(...)
```

The repository would handle the actual PostgreSQL query.

This should keep the service code focused more on billing decisions instead of database details.

I am not planning to build a completely generic repository framework. The repository functions will just cover the database operations this project actually needs.

---

## Main Application Flows

### Billable Request

The main `/generate` flow should roughly look like this:

```text
POST /generate
      |
      v
Validate request
      |
      v
Authenticate tenant
      |
      v
Check Idempotency-Key
      |
      +------ duplicate ------> Return existing result
      |
      v
Load subscription + plan
      |
      v
Check current usage + quota
      |
      +------ over limit -----> Return 429 / 402
      |
      v
Calculate cost
      |
      v
Store usage event
      |
      v
Return result
```

This is probably the most important flow in the project because it connects idempotency, quotas, pricing, and persistence.

---

### Usage Summary

The `/usage` flow should be simpler:

```text
GET /usage
     |
     v
Authenticate tenant
     |
     v
Load plan + subscription
     |
     v
Read current-period usage events
     |
     v
Calculate totals
     |
     v
Return used / limit / cost
```

For now, I will calculate the totals from the usage events each time instead of maintaining a separate summary table.

---

### Stripe Webhook

The Stripe webhook flow should look roughly like:

```text
Stripe
  |
  v
POST /webhooks/stripe
  |
  v
Verify signature
  |
  +------ invalid ------> 400
  |
  v
Check Stripe event ID
  |
  +------ duplicate ----> Ignore safely
  |
  v
Process supported event
  |
  v
Update subscription
  |
  v
Record processed event ID
```

I want the signature check to happen before making any subscription changes.

The client should not be able to directly tell the backend that a Stripe payment succeeded.

---

## Planned Project Structure

The project structure will probably start similar to this:

```text
app/
├── main.py
├── api/
│   ├── health.py
│   ├── usage.py
│   ├── billing.py
│   └── webhooks.py
├── services/
│   ├── meter_service.py
│   ├── quota_service.py
│   ├── pricing_service.py
│   └── subscription_service.py
├── repositories/
│   ├── tenant_repository.py
│   ├── plan_repository.py
│   ├── subscription_repository.py
│   ├── usage_repository.py
│   └── stripe_event_repository.py
├── models/
├── schemas/
├── jobs/
├── config.py
└── database.py

tests/
```

This is only the planned structure.

I may combine or rename some files if they end up being very small. I do not want to create a bunch of files just for the sake of having more layers.

The important part is that the API, billing logic, and database access stay reasonably separated.

---

## Background Job Plan

The shared capstone requirements ask for at least one background job.

I do not need the background job for the main metering request itself, because usage and quota checks need to happen immediately.

Later in the project, I plan to add one small background task related to billing maintenance or reconciliation.

The exact job will be decided once the core billing and Stripe flows are working.

I am leaving this slightly open for now because I do not want to design a complicated job before I know what the application actually needs.

---

## Explicit Non-Goal

This project is not meant to be a complete production billing platform.

The core version will **not** implement:

- Real payments
- Invoices
- Proration
- Overage billing
- Multiple currencies
- A customer billing frontend
- A full user account/login system
- Real AI model calls
- A complete history of every subscription change

Stripe will only run in test mode.

AI-token usage will also be simulated instead of calling an actual AI provider.

The main goal is to learn and demonstrate the parts that are important to this capstone:

- Usage metering
- Idempotency
- Quota enforcement
- Correct cost calculations
- Tenant separation
- Stripe webhook verification
- Duplicate webhook handling

There are more features that could make this closer to a real billing product, but I would rather have a smaller project where these core parts work correctly and are well tested.