# MEOK Stripe ACP Checkout MCP

> ## 🧱 Part of the MEOK A2A Substrate (£999/mo)
> See [meok.ai/a2a](https://meok.ai/a2a).

# Stripe Agentic Commerce Protocol — ChatGPT shopping bridge

<!-- mcp-name: io.github.CSOAI-ORG/meok-stripe-acp-checkout-mcp -->

[![PyPI](https://img.shields.io/pypi/v/meok-stripe-acp-checkout-mcp)](https://pypi.org/project/meok-stripe-acp-checkout-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## What this bridges

**Stripe Agentic Commerce Protocol (ACP)** — the merchant-side spec for ChatGPT shopping + Claude shopping + agentic checkout. Launched Sept 2025 with OpenAI. 60+ launch partners by Mar 2026 (Shopify, Etsy, Instacart, DoorDash, Uber Eats, Ticketmaster, Expedia, Wayfair, Target, …).

This MCP issues + verifies + signs Stripe ACP checkout intents, crosswalks against AP2 mandates (`meok-ap2-mandate-mcp`), enforces PSD2 SCA, and emits audit-defensible receipts.

## Tools

| Tool | Purpose |
|---|---|
| `list_acp_catalogue(merchant_id, category?)` | Fetch merchant's ACP product catalogue |
| `create_checkout_intent(cart, customer_did, merchant_id, currency, ap2_mandate_id?)` | New checkout intent |
| `verify_intent_against_mandate(intent_id, mandate_id, mandate_remaining_eur)` | Cross-check vs AP2 cap |
| `request_delegated_payment(intent_id, payment_method_id, sca_method)` | Stripe-hosted SCA flow |
| `emit_signed_receipt(intent_id, stripe_charge_id)` | HMAC-signed receipt |
| `list_acp_partners()` | 60+ known ACP-enabled merchants |

## Sister MCPs

- `meok-ap2-mandate-mcp` — Google AP2 user-side spend authorisation (pairs perfectly)
- `agent-commerce-protocol-mcp` — multi-protocol commerce bridge (ACP / AP2 / x402)
- `agent-x402-paywall-mcp` — Coinbase HTTP 402 on-chain settlement
- `meok-x402-wrap-mcp` — 1-line USDC paywall

Full catalogue: [meok.ai/anthropic-registry](https://meok.ai/anthropic-registry)

## Pricing

| Option | Price |
|---|---|
| Self-host MIT | £0 |
| Universal PAYG | £29/mo + £0.0002/call |
| A2A Substrate | £999/mo |
| Defence | £4,990/mo |

Buy: https://meok.ai/a2a

## Wire it up — full stack

The agentic-checkout signed pipeline:

1. **meok-ap2-mandate-mcp** — user signs spend authorisation
2. **agent-policy-enforcement-mcp** — IAM gate per call
3. **meok-stripe-acp-checkout-mcp** — this MCP (creates Stripe ACP intent)
4. **agent-commerce-payments-mcp** — PSD2 + MiCA payment rails
5. **agent-audit-logger-mcp** — hash-chained evidence
6. **a2a-governance-bridge-mcp** — fold into 1 signed event

See [meok.ai/mcp-stack](https://meok.ai/mcp-stack).

## Licence

MIT. By [MEOK AI Labs](https://meok.ai) (CSOAI LTD, UK Companies House 16939677).
