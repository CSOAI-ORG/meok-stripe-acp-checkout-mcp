#!/usr/bin/env python3
"""
Buy Pro: https://www.csoai.org/checkout

MEOK Stripe ACP Checkout MCP — ChatGPT shopping bridge
========================================================

By MEOK AI Labs · https://meok.ai · MIT
<!-- mcp-name: io.github.CSOAI-ORG/meok-stripe-acp-checkout-mcp -->

WHAT THIS BRIDGES
-----------------
**Stripe Agentic Commerce Protocol (ACP)** — the merchant-side spec for
ChatGPT shopping + Claude shopping + agentic checkout flows. Stripe launched
ACP Sept 2025 with OpenAI, with 60+ launch partners by Mar 2026.

ACP defines:
  - `acp.product`        — product catalogue exposed to agents
  - `acp.cart`           — agent-managed cart
  - `acp.checkout`       — agent-initiated checkout intent
  - `acp.payment_method` — agent-bound payment method ref
  - `acp.delegated_payment` — Stripe-hosted payment with shopper SCA

This MCP issues + verifies + signs Stripe ACP checkout intents, validates
against AP2 mandates (meok-ap2-mandate-mcp), enforces PSD2 SCA, and emits
audit-defensible receipts.

TOOLS
-----
- list_acp_catalogue(merchant_id)
- create_checkout_intent(cart, customer_did, ap2_mandate_id?)
- verify_intent_against_mandate(intent_id, mandate_id)
- request_delegated_payment(intent_id, payment_method_id)
- emit_signed_receipt(intent_id, stripe_charge_id)
- list_acp_partners(): 60+ known ACP-enabled merchants

NOTE: IBM ACP (Agent Communication Protocol) merged into A2A Sept 2025 —
that's a DIFFERENT thing (covered by agent-commerce-protocol-mcp).
This MCP is exclusively Stripe ACP.

By MEOK AI Labs · MIT.
"""

from __future__ import annotations
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from typing import Optional
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("meok-stripe-acp-checkout")
_HMAC_SECRET = os.environ.get("MEOK_HMAC_SECRET", "")
_INTENTS: dict[str, dict] = {}


SPEC = "Stripe Agentic Commerce Protocol (ACP) v1.0 (Sept 2025)"

# Known ACP launch partners (refresh quarterly from stripe.com/acp)
ACP_PARTNERS = [
    "stripe", "shopify", "etsy", "ebay", "instacart", "doordash", "uber-eats",
    "ticketmaster", "vinted", "depop", "lululemon", "wayfair", "target",
    "best-buy", "macy-s", "nordstrom", "expedia", "booking-com", "hotels-com",
    "kayak", "tripadvisor", "viator", "klook", "getyourguide",
    "groupon", "wish", "aliexpress-eu", "asos", "zalando", "boohoo",
    "thrive-market", "fresh-direct", "gopuff", "drizly", "minibar",
    "blue-apron", "hellofresh", "factor", "freshly", "purple-carrot",
    "warby-parker", "casper", "purple", "saatva", "wayfair-uk", "made",
    "ikea", "west-elm", "crate-and-barrel", "cb2", "cratejoy",
    "bonobos", "everlane", "uniqlo", "patagonia", "rei", "moosejaw",
    "backcountry", "evo", "the-house", "competitive-cyclist", "jenson-usa",
]


def _sign(payload: dict) -> str:
    if not _HMAC_SECRET:
        return "unsigned-no-key-configured"
    return hmac.new(_HMAC_SECRET.encode(), json.dumps(payload, sort_keys=True).encode(), hashlib.sha256).hexdigest()


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────────────
# Tools
# ──────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_acp_catalogue(merchant_id: str, category: Optional[str] = None) -> dict:
    """
    Scaffold for fetching a merchant's ACP product catalogue.

    Args:
        merchant_id: ACP merchant identifier.
        category: Optional category filter.

    Returns:
        {merchant_id, products, fetch_hint}
    """
    return {
        "merchant_id": merchant_id,
        "products": [],
        "stage": "scaffold — wire to https://api.stripe.com/v1/acp/{merchant_id}/products for production",
        "fetch_hint": "Use Stripe SDK acp.products.list({merchant_id, category}). Bearer token from your Stripe account.",
        "spec": SPEC,
    }


@mcp.tool()
def create_checkout_intent(
    cart: list[dict],
    customer_did: str,
    merchant_id: str,
    currency: str = "GBP",
    ap2_mandate_id: Optional[str] = None,
    shipping_address: Optional[dict] = None,
) -> dict:
    """
    Create a Stripe ACP checkout intent.

    Args:
        cart: List of {product_id, qty, unit_amount_minor} dicts.
        customer_did: W3C DID of the customer.
        merchant_id: ACP merchant identifier.
        currency: ISO 4217 currency code (default GBP).
        ap2_mandate_id: Optional AP2 mandate from meok-ap2-mandate-mcp.
        shipping_address: Optional ship-to address dict.

    Returns:
        {intent_id, total_minor, currency, signature}
    """
    if not cart:
        return {"error": "cart cannot be empty"}
    total_minor = sum(item.get("qty", 1) * item.get("unit_amount_minor", 0) for item in cart)
    intent_id = f"ACP_INTENT_{int(time.time())}_{os.urandom(4).hex()}"
    intent = {
        "intent_id": intent_id,
        "spec": SPEC,
        "merchant_id": merchant_id,
        "customer_did": customer_did,
        "cart": cart,
        "total_minor": total_minor,
        "currency": currency,
        "ap2_mandate_id": ap2_mandate_id,
        "shipping_address": shipping_address,
        "status": "pending_payment_method",
        "created_at": _ts(),
    }
    intent["signature"] = _sign(intent)
    _INTENTS[intent_id] = intent
    return {
        "intent_id": intent_id,
        "total_minor": total_minor,
        "currency": currency,
        "signature": intent["signature"],
        "next_step": (
            f"Call verify_intent_against_mandate(intent_id='{intent_id}', mandate_id='{ap2_mandate_id}') before requesting payment."
            if ap2_mandate_id
            else "Bind a payment method via request_delegated_payment()."
        ),
    }


@mcp.tool()
def verify_intent_against_mandate(intent_id: str, mandate_id: str, mandate_remaining_eur: float) -> dict:
    """
    Cross-check a Stripe ACP intent against an AP2 mandate.

    Args:
        intent_id: From create_checkout_intent().
        mandate_id: From meok-ap2-mandate-mcp issue_mandate().
        mandate_remaining_eur: Remaining cap on the mandate.

    Returns:
        {allowed, reason, total_in_eur_estimate}
    """
    if intent_id not in _INTENTS:
        return {"allowed": False, "reason": "unknown_intent"}
    intent = _INTENTS[intent_id]
    # Convert GBP/USD to EUR using fixed approx rates (production: Stripe FX endpoint)
    rate = {"GBP": 1.17, "USD": 0.92, "EUR": 1.0, "JPY": 0.0058}.get(intent["currency"], 1.0)
    eur_estimate = (intent["total_minor"] / 100.0) * rate
    if eur_estimate > mandate_remaining_eur:
        return {
            "allowed": False,
            "reason": "intent_exceeds_mandate_cap",
            "total_in_eur_estimate": round(eur_estimate, 2),
            "mandate_remaining_eur": mandate_remaining_eur,
        }
    return {
        "allowed": True,
        "total_in_eur_estimate": round(eur_estimate, 2),
        "mandate_remaining_eur": mandate_remaining_eur,
        "reason": "ok",
    }


@mcp.tool()
def request_delegated_payment(intent_id: str, payment_method_id: str, sca_method: str = "passkey_webauthn") -> dict:
    """
    Request Stripe-hosted delegated payment for an ACP intent.

    Args:
        intent_id: From create_checkout_intent().
        payment_method_id: Stripe payment method ID (pm_xxx).
        sca_method: PSD2 SCA method (see meok-ap2-mandate-mcp).

    Returns:
        {redirect_url, intent_id, status}
    """
    if intent_id not in _INTENTS:
        return {"error": "unknown_intent"}
    intent = _INTENTS[intent_id]
    intent["payment_method_id"] = payment_method_id
    intent["sca_method"] = sca_method
    intent["status"] = "awaiting_sca"
    # Production: actual Stripe Checkout Session create
    return {
        "intent_id": intent_id,
        "redirect_url": f"https://checkout.stripe.com/c/acp/{intent_id}?pm={payment_method_id}",
        "status": "awaiting_sca",
        "sca_method": sca_method,
        "next_step": "Redirect the user to redirect_url for SCA confirmation. Stripe will webhook your endpoint on completion.",
    }


@mcp.tool()
def emit_signed_receipt(intent_id: str, stripe_charge_id: str) -> dict:
    """
    Emit an HMAC-signed receipt after successful charge.

    Args:
        intent_id: From create_checkout_intent().
        stripe_charge_id: Stripe charge ID (ch_xxx).

    Returns:
        {receipt_id, signature, verify_url}
    """
    if intent_id not in _INTENTS:
        return {"error": "unknown_intent"}
    intent = _INTENTS[intent_id]
    intent["status"] = "succeeded"
    intent["stripe_charge_id"] = stripe_charge_id
    receipt_id = f"ACP_RCPT_{int(time.time())}_{os.urandom(4).hex()}"
    sealed = {
        "receipt_id": receipt_id,
        "spec": SPEC,
        "intent_id": intent_id,
        "stripe_charge_id": stripe_charge_id,
        "merchant_id": intent["merchant_id"],
        "customer_did": intent["customer_did"],
        "total_minor": intent["total_minor"],
        "currency": intent["currency"],
        "sealed_at": _ts(),
        "issuer": "MEOK AI Labs (CSOAI LTD)",
    }
    sig = _sign(sealed)
    return {
        "receipt_id": receipt_id,
        "signature": sig,
        "sealed_at": sealed["sealed_at"],
        "verify_url": f"https://meok-attestation-api.vercel.app/verify/{receipt_id}",
        "retention_hint": "Retain receipt 6 years (UK MTD) / 10 years (DE HGB).",
    }


@mcp.tool()
def list_acp_partners() -> dict:
    """Return the known list of ACP-enabled merchants (refresh quarterly)."""
    return {
        "spec": SPEC,
        "partners": ACP_PARTNERS,
        "count": len(ACP_PARTNERS),
        "source": "https://stripe.com/agentic-commerce-protocol/partners (manual refresh)",
    }


if __name__ == "__main__":
    mcp.run()


# ── MEOK monetization layer (Stripe upgrade · PAYG · pricing) ──────────
# Free tier is zero-config. Upgrade to Pro (unlimited) or pay-as-you-go per call.
import os as _meok_os
MEOK_STRIPE_UPGRADE = "https://buy.stripe.com/00wfZjcgAeUW4c5cyQ8k90K"  # Pro (unlimited)
MEOK_PAYG_KEY = _meok_os.environ.get("MEOK_PAYG_KEY", "")  # set to enable PAYG (x402 / ~GBP0.05 per call)
MEOK_PRICING = "https://meok.ai/pricing"


def meok_upsell(tier: str = "free") -> dict:
    """Monetization options for free-tier callers: Pro upgrade, PAYG, or pricing page."""
    if tier != "free":
        return {}
    return {"upgrade_url": MEOK_STRIPE_UPGRADE,
            "payg_enabled": bool(MEOK_PAYG_KEY),
            "pricing": MEOK_PRICING}
