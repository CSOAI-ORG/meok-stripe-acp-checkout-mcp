"""Smoke tests for meok-stripe-acp-checkout-mcp."""
import sys, os, inspect, traceback
os.environ.setdefault("MEOK_HMAC_SECRET", "test-only-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import (
    list_acp_catalogue,
    create_checkout_intent,
    verify_intent_against_mandate,
    request_delegated_payment,
    emit_signed_receipt,
    list_acp_partners,
    _INTENTS,
)


def test_list_catalogue_returns_scaffold():
    r = list_acp_catalogue("shopify", "books")
    assert r["merchant_id"] == "shopify"
    assert "Stripe" in r["spec"] or "ACP" in r["spec"]


def test_create_checkout_intent_basic():
    _INTENTS.clear()
    r = create_checkout_intent(
        cart=[{"product_id": "prod_1", "qty": 2, "unit_amount_minor": 2999}],
        customer_did="did:web:customer.example",
        merchant_id="shopify",
    )
    assert r["intent_id"].startswith("ACP_INTENT_")
    assert r["total_minor"] == 5998


def test_create_checkout_intent_empty_cart_fails():
    _INTENTS.clear()
    r = create_checkout_intent(cart=[], customer_did="x", merchant_id="y")
    assert "error" in r


def test_verify_intent_within_mandate():
    _INTENTS.clear()
    intent = create_checkout_intent(
        cart=[{"product_id": "x", "qty": 1, "unit_amount_minor": 5000}],
        customer_did="did:x", merchant_id="shopify", currency="GBP",
    )
    r = verify_intent_against_mandate(intent["intent_id"], "AP2_FAKE", mandate_remaining_eur=200.0)
    assert r["allowed"] is True


def test_verify_intent_exceeds_mandate():
    _INTENTS.clear()
    intent = create_checkout_intent(
        cart=[{"product_id": "x", "qty": 1, "unit_amount_minor": 50000}],
        customer_did="did:x", merchant_id="shopify", currency="GBP",
    )
    r = verify_intent_against_mandate(intent["intent_id"], "AP2_FAKE", mandate_remaining_eur=100.0)
    assert r["allowed"] is False


def test_verify_intent_unknown():
    r = verify_intent_against_mandate("nope", "AP2", 100.0)
    assert r["allowed"] is False


def test_request_delegated_payment():
    _INTENTS.clear()
    intent = create_checkout_intent(
        cart=[{"product_id": "x", "qty": 1, "unit_amount_minor": 1000}],
        customer_did="did:x", merchant_id="shopify",
    )
    r = request_delegated_payment(intent["intent_id"], "pm_abc123")
    assert "checkout.stripe.com" in r["redirect_url"]
    assert r["status"] == "awaiting_sca"


def test_emit_signed_receipt():
    _INTENTS.clear()
    intent = create_checkout_intent(
        cart=[{"product_id": "x", "qty": 1, "unit_amount_minor": 1000}],
        customer_did="did:x", merchant_id="shopify",
    )
    r = emit_signed_receipt(intent["intent_id"], "ch_test_charge_id")
    assert r["receipt_id"].startswith("ACP_RCPT_")
    assert "verify_url" in r


def test_emit_receipt_unknown_intent():
    r = emit_signed_receipt("nope", "ch_x")
    assert "error" in r


def test_list_acp_partners():
    r = list_acp_partners()
    assert r["count"] >= 50
    assert "stripe" in r["partners"]
    assert "shopify" in r["partners"]


if __name__ == "__main__":
    g = dict(globals())
    fns = [v for k, v in g.items() if k.startswith("test_") and inspect.isfunction(v)]
    p = f = 0
    for fn in fns:
        try:
            fn(); print(f"OK {fn.__name__}"); p += 1
        except Exception as e:
            print(f"X  {fn.__name__}: {type(e).__name__}: {e}"); traceback.print_exc(); f += 1
    print(f"\n{p} passed, {f} failed")
