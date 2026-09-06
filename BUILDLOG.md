# Build Log

This file documents how I used AI while building the Usage Metering & Billing Engine capstone.

I used ChatGPT mainly as a second set of eyes while working through the project. I used it to discuss design choices, review code, help interpret errors, suggest test cases, and improve documentation. I made the final implementation decisions, wrote and organized the project in my repository, ran all commands and tests locally, and changed suggestions when they did not fit the project or caused issues.

## Phase 1 - Design

I started by breaking the capstone requirements into the main parts I needed to support: tenants, plans, subscriptions, usage events, quota enforcement, pricing, and Stripe synchronization.

I decided to use:

- FastAPI for the API
- PostgreSQL for persistence
- SQLAlchemy for database access
- Alembic for migrations
- Stripe test mode for subscriptions
- API keys for tenant authentication
- a basic API -> service -> repository -> database structure

I used AI mostly to review the design and point out cases I needed to think about, especially idempotency and quota boundaries.

Some design choices I intentionally kept simple were:

- keeping all SQLAlchemy models in `models.py`
- using foreign keys without adding ORM relationships everywhere
- using one API key per tenant
- using a calendar month for usage totals
- storing individual usage events instead of maintaining a separate running counter

I considered more complicated alternatives, but I kept the design small enough that I could understand and explain every part of it.

## Phase 2 - Metering and Quotas

I built the FastAPI and PostgreSQL setup first, then added the models, migrations, seed data, tenant authentication, metering, and quota checks in smaller steps.

I used AI during this phase mostly for reviewing code, suggesting test cases, and helping debug errors.

One issue was how I ran the seed script. Running:

`python scripts/seed.py`

caused an import problem with my project structure.

I changed the command to:

`python -m scripts.seed`

and used that module-style command for the other scripts in the project as well.

I also chose not to use `__init__.py` files in the project structure.

For usage idempotency, I implemented two protections:

- an application-level lookup for an existing tenant/idempotency-key pair
- a database unique constraint on the tenant and idempotency key

I also catch `IntegrityError` in case two requests using the same key reach the insert at nearly the same time.

For quota testing, I manually seeded the demo tenant close to its Free plan API limit and tested:

`999 -> 1000` = allowed

`1000 -> 1001` = rejected with 429

After confirming it manually, I wrote automated tests using smaller test quotas so the same boundary rule could be tested without creating 1,000 rows every time.

I also added AI token usage as the second metered usage type and stored the different token categories separately.

One thing I intentionally did not solve is the race between two different requests arriving at the exact quota boundary. The quota read and usage insert are not one atomic operation. Fixing that could involve database locking or a separate atomic usage counter, but I left it as a limitation rather than adding that complexity to this version.

## Phase 3 - Stripe Integration

I added Stripe Checkout in test mode for upgrading a tenant to the Pro plan.

One design decision I kept from the beginning was that calling `/billing/checkout` does not directly change the tenant's plan. It only creates the Stripe Checkout Session.

The plan is changed after the application receives a verified Stripe webhook.

I implemented webhook handling for:

- `checkout.session.completed`
- `customer.subscription.updated`
- `customer.subscription.deleted`

I also added Stripe signature verification and stored processed Stripe event IDs so the same event would not be processed twice.

This phase had the most debugging.

One problem was caused by treating a Stripe `Session` object like a normal Python dictionary:

`session.get(...)`

That resulted in a 500 error. After checking the traceback, I found that the Stripe object needed to be converted using:

`.to_dict()`

I changed the handler to convert the Stripe objects before reading their fields.

I also introduced an indentation/control-flow bug while adding the different webhook event branches. A variable created only for Checkout events was being accessed during a subscription deletion event. I reorganized the handler into separate `if / elif` branches so each event type only uses the data that belongs to it.

I also had to troubleshoot the Stripe CLI listener and sandbox configuration while testing local webhooks.

The Stripe flow I eventually verified was:

- Free -> Pro after a completed Stripe Checkout
- subscription updates stay synchronized
- deleted Pro subscription -> Free
- invalid webhook signature -> 400
- valid Stripe events -> 200
- repeated Stripe event IDs are not processed twice

AI was useful here for interpreting tracebacks and talking through possible causes, but I used the actual terminal output and Stripe event data to determine what was failing.

## Phase 4 - Pricing and Usage

I added pricing after the metering behavior was already working.

I chose to store money as integer micro-USD values instead of using floating-point dollar amounts.

I pinned the pricing constants in the project instead of reading current provider pricing dynamically. This makes the calculations deterministic and keeps the tests from changing if provider pricing changes later.

The AI usage pricing keeps these categories separate:

- regular input tokens
- cached input tokens
- output tokens
- reasoning tokens

Cached input is priced at its lower rate, while reasoning tokens use the output-token rate.

I wrote pricing tests that check:

- API-call pricing
- regular input pricing
- cached input pricing
- output pricing
- reasoning-token pricing
- mixed token categories
- zero usage
- invalid negative values

After the pricing tests were working, I connected the pricing service to the metering service so new usage events store their calculated `cost_microusd`.

I then added `GET /usage`, which returns the authenticated tenant's:

- current plan
- subscription status
- API calls used and limit
- AI tokens used and limit
- total monthly cost

I also added a tenant-isolation test. The test creates usage for two different tenants and verifies that one tenant's `/usage` response does not include the other tenant's activity.

## Background Job

The capstone also requires work that runs outside the HTTP request path.

I considered using something like Celery and Redis, but that would add a large amount of infrastructure for the one maintenance task I needed.

Instead, I created a usage reconciliation job.

It can be run with:

`python -m scripts.run_recon`

The job scans tenants and calculates their current monthly:

- API usage
- AI token usage
- usage cost

It also retries temporary failures up to three times.

I added an automated test that forces the first two reconciliation attempts to fail and verifies that the third succeeds. The test replaces the real sleep call so the test does not have to wait during retries.

I used the shorter filenames:

- `app/jobs/usage_recon.py`
- `scripts/run_recon.py`
- `tests/test_urecon.py`

## How I Used AI

My main uses of AI during this project were:

- discussing design tradeoffs before implementing them
- reviewing pieces of code after I wrote or modified them
- helping interpret Python, SQLAlchemy, FastAPI, and Stripe errors
- suggesting edge cases worth testing
- checking calculations
- helping organize documentation
- providing starting examples that I could modify for my project

I did not treat generated code as automatically correct. There were multiple cases where suggestions had to be changed after testing them, including the seed-script command, Stripe object handling, and webhook control flow.

Running the application, inspecting database state, testing API responses, reading tracebacks, and deciding whether the behavior matched the capstone requirements were all part of my own development process.

## Known Limitations

This project is meant to demonstrate the core billing and metering concepts rather than act as a complete production billing platform.

Current limitations include:

- no real money movement
- no invoicing
- no proration
- no overage billing
- no multiple currencies
- no complete API-key rotation system
- no complete subscription history
- no dedicated PostgreSQL test container
- no distributed task queue
- no atomic quota counter for different concurrent requests at the exact boundary
- no request-payload hash when an idempotency key is reused
- usage periods use the calendar month instead of the exact Stripe billing period
- development usage events created before pricing was implemented still have a cost of 0

I left these out so I could focus on the parts the capstone is centered around: idempotent metering, quota enforcement, correct pricing, Stripe subscription synchronization, tenant isolation, and tests for important failure cases.