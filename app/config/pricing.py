# Pricing is pinned for this project so historical calculations
# stay deterministic even if provider pricing changes later.
#
# Reference:
# Gemini 2.5 Flash - Standard paid tier
# Pricing snapshot: 2026-09-01

TOKENS_PER_PRICE_UNIT = 1_000_000

# All prices are stored as micro-USD per 1 million tokens.
# $1.00 = 1,000,000 micro-USD.
INPUT_PRICE_MICROUSD_PER_MILLION = 300_000
CACHED_INPUT_PRICE_MICROUSD_PER_MILLION = 30_000
OUTPUT_PRICE_MICROUSD_PER_MILLION = 2_500_000

# API-call pricing is project-defined rather than provider-defined.
# 100 micro-USD = $0.0001 per API call.
API_CALL_PRICE_MICROUSD = 100