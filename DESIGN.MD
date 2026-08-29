# Usage Metering & Billing Engine — Design

## Problem Statement

SaaS applications need to accurately track how much each customer uses, determine whether that usage is within the limits of their subscription plan, and calculate the associated cost.

Retries, duplicate requests, and repeated payment webhooks can cause incorrect usage totals or duplicate charges if they are not handled carefully.

This project will build a multi-tenant usage metering and billing service that:

- Records API and AI-token usage
- Prevents duplicate usage events through idempotency
- Enforces Free and Pro plan quotas
- Calculates usage costs using deterministic pricing rules
- Synchronizes subscription state with Stripe test mode through verified and deduplicated webhooks

The project focuses on correctness under retries, quota boundaries, and duplicate events rather than building a complete commercial billing platform.

## Core Success Criteria

The system should meet the following goals:

1. A retried billable request records exactly one usage event.
2. Requests that would exceed a tenant's quota are rejected with a clear response.
3. A request that brings a tenant exactly to its quota is allowed.
4. Usage and cost calculations are deterministic and testable.
5. Stripe subscription updates are accepted only from verified webhook events.
6. Replaying the same Stripe webhook does not apply the update twice.