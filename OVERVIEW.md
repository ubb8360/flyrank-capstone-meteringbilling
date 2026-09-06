# Capstone Overview

## Usage Metering & Billing Engine

For my Backend AI Engineering capstone, I built a backend service that tracks customer usage, enforces plan limits, calculates usage costs, and keeps subscription status synchronized with Stripe test mode.

The main problem I wanted to solve was something that almost every API or SaaS product has to deal with: knowing how much a customer has used, whether they are still within their plan, and what that usage costs.

I kept the project intentionally small so I could focus on the backend behavior instead of trying to build a full billing platform.

## What I Built

The project supports two plans:

- Free
- Pro

It also tracks two types of usage:

- API calls
- AI token usage

Each tenant has an API key. When a billable request is made, the service checks the tenant, checks the current subscription, checks the monthly quota, calculates the cost, and stores a usage event.

The main billable endpoint is:

`POST /generate`

It does not call a real AI model. Instead, it simulates billable usage so I could focus on the metering and billing logic.

For AI usage, I keep these token categories separate:

- input tokens
- cached input tokens
- output tokens
- reasoning tokens

This mattered because cached input is priced differently, while reasoning tokens are priced using the output rate.

## Main Features

Some of the main things I implemented were:

- API key authentication for tenants
- idempotent usage tracking
- API call and AI token quotas
- 429 responses when a tenant goes over quota
- 402 responses when a subscription is not active
- integer micro-USD cost calculations
- monthly usage and cost rollups
- Stripe Checkout in test mode
- Stripe webhook signature verification
- Stripe event deduplication
- Free to Pro subscription updates
- subscription cancellation back to Free
- tenant-isolated usage queries
- a small usage reconciliation background job
- PostgreSQL migrations with Alembic

I also wrote automated tests for the main metering, pricing, usage, authentication, and reconciliation behavior. My final test run had 20 passing tests.

## Tech Stack

I used:

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Docker
- Stripe Test Mode
- Stripe CLI
- Pytest

I split the project into basic layers:

```text
API Routes
    |
    v
Services
    |
    v
Repositories
    |
    v
PostgreSQL
```

I liked this structure because it kept the HTTP code separate from the main business logic and database queries.

## Idempotency and Quotas

One part of the project I spent time on was preventing duplicate usage.

Each billable request includes an `Idempotency-Key`. If the same tenant sends the same key again, the existing usage event is returned instead of creating another one.

I also added a database unique constraint on:

`(tenant_id, idempotency_key)`

so the database gives another layer of protection.

For quotas, I used this rule:

`current usage + requested usage <= plan limit`

That means a Free tenant at 999 API calls can make one more request and reach 1000, but the next request is rejected.

I manually tested that boundary and also covered it with automated tests.

## Pricing

I decided to store money as integer micro-USD values instead of floats.

The pricing values are pinned in the project so the tests stay deterministic even if provider pricing changes later.

The current project pricing is:

- API call: 100 microUSD per call
- input tokens: $0.30 per 1M tokens
- cached input tokens: $0.03 per 1M tokens
- output tokens: $2.50 per 1M tokens
- reasoning tokens: $2.50 per 1M tokens

`GET /usage` returns the tenant's current plan, subscription status, usage totals, limits, and monthly cost.

## Stripe Integration

Stripe is used in test mode.

A tenant can start a Pro upgrade through:

`POST /billing/checkout`

That endpoint creates a Stripe Checkout Session, but it does not directly change the tenant to Pro.

The local subscription only changes after the application receives a verified Stripe webhook.

I handle:

- `checkout.session.completed`
- `customer.subscription.updated`
- `customer.subscription.deleted`

I also verify Stripe signatures and store processed Stripe event IDs so the same event is not handled twice.

During development, this was one of the harder parts of the project because I had to debug Stripe objects, webhook event flow, and the Stripe CLI listener.

## Background Job

I added a small usage reconciliation job that runs separately from the FastAPI request path.

It can be run with:

`python -m scripts.run_recon`

The job goes through tenants and reports their monthly API usage, AI token usage, and cost.

It retries failures up to three times.

I kept this simple instead of adding a larger queue system like Celery and Redis because I only needed one maintenance-style job for this project.

## What I Learned

This project helped me understand how several backend ideas connect together in one system instead of being separate examples.

The biggest areas I worked with were:

- designing a database around tenant-owned data
- enforcing quotas before recording usage
- handling retries safely with idempotency
- using integer values for money calculations
- separating API, service, and repository code
- working with Stripe Checkout and webhooks
- debugging external service behavior with real event data
- writing tests around edge cases instead of only the happy path

I also got more comfortable reading tracebacks and checking the database directly when something did not behave the way I expected.

## Limitations

This is not meant to be a complete production billing platform.

Some things I intentionally did not build are:

- real payments or invoicing
- overage billing
- proration
- multiple currencies
- API key rotation
- full subscription history
- a distributed task queue
- a dedicated PostgreSQL test container
- payload hashing for reused idempotency keys
- a fully atomic quota counter for different requests racing at the exact limit

Usage also follows the calendar month instead of the exact Stripe billing period.

I kept these limitations so I could focus on the core problem: tracking usage correctly, enforcing access limits, calculating cost, and keeping customer subscription state synchronized.
