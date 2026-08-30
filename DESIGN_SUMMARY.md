# Usage Metering & Billing Engine — Design Summary

## Problem

This project is a small backend billing service for tracking how much a customer uses, checking whether they are within their subscription limits, and calculating the cost of that usage.

The main issue I am trying to solve is making sure usage stays correct when requests are retried or events are sent more than once. A duplicate request should not create duplicate usage, and a duplicate Stripe webhook should not update a subscription twice.

The core project will support:

- Free and Pro plans
- API-call usage
- Simulated AI-token usage
- Monthly quota enforcement
- Usage cost calculation
- Stripe test-mode subscription updates

The main focus is correctness and being able to clearly test the important edge cases.

---

## Data Model

The project will use PostgreSQL.

Main tables:

| Table | Purpose |
| --- | --- |
| `tenants` | Stores each customer and their API-key hash |
| `plans` | Stores Free and Pro plan limits |
| `subscriptions` | Stores the tenant's current plan and Stripe subscription information |
| `usage_events` | Stores individual billable actions |
| `stripe_events` | Stores processed Stripe event IDs to prevent duplicate webhook handling |

Each `usage_event` belongs to a tenant.

Instead of storing only a running usage counter, I will keep individual usage events so I can see where totals came from and make the metering logic easier to test.

Usage events will have a unique constraint on:

`(tenant_id, idempotency_key)`

This provides database-level protection against recording the same logical request twice.

Money will be stored using integer units instead of floating-point values.

---

## Plans

The starting limits will be:

| Plan | API Calls / Month | AI Tokens / Month |
| --- | ---: | ---: |
| Free | 1,000 | 100,000 |
| Pro | 10,000 | 1,000,000 |

The Free limits come from the capstone requirements.

The Pro limits are project-defined because the brief only requires them to be higher than Free. I chose simple values that should be easy to test and demonstrate.

A request that brings usage exactly to the limit will be allowed.

A request that would go over the limit will be rejected.

---

## API Surface

The core API will stay fairly small.

- `GET /health` — check that the API is running
- `POST /generate` — dummy billable endpoint used to simulate API or AI-token usage
- `GET /usage` — return current usage, limits, plan, and cost
- `POST /billing/checkout` — create a Stripe test-mode Checkout session
- `POST /webhooks/stripe` — receive and verify Stripe subscription events

Every billable request to `POST /generate` will require an `Idempotency-Key`.

If the same request is retried with the same key, the existing usage result should be returned instead of creating another event.

For quota responses:

- `429 Too Many Requests` = usage quota problem
- `402 Payment Required` = subscription or payment-state problem

Stripe subscription changes will only happen after receiving a verified webhook. The client will not be allowed to directly set itself to the Pro plan.

---

## Architecture

The project will use a basic layered structure:

    Client / Stripe
          |
          v
      API Layer
          |
          v
     Service Layer
          |
          v
    Repository Layer
          |
          v
      PostgreSQL

The API layer will handle FastAPI requests, validation, authentication, and HTTP responses.

The service layer will contain the main billing logic, such as metering, quota checks, pricing, and subscription updates.

The repository layer will contain PostgreSQL queries.

The goal is to keep the billing rules separate from the HTTP routes and database code without adding more abstraction than the project needs.

The planned main services are:

- `MeterService`
- `QuotaService`
- `PricingService`
- `SubscriptionService`

I may combine or rename some parts while implementing if the initial structure ends up being more complicated than necessary.

---

## Background Job

The shared capstone requirements include at least one background job.

The core metering path needs to happen immediately, so I do not plan to move quota checking or usage recording into a background job.

Instead, I will add one small billing maintenance or reconciliation job later after the main metering and Stripe features are working.

I am leaving the exact job open for now so I do not add unnecessary complexity before the core system is built.

---

## Explicit Non-Goal

This project is not intended to become a complete production billing platform.

The core version will not include real payments, invoicing, proration, overage billing, multiple currencies, a customer billing frontend, or real AI model calls.

Stripe will only be used in test mode, and AI-token usage will be simulated.

I would rather keep the project smaller and make the core metering, quota, idempotency, pricing, and Stripe webhook behavior correct and well tested.