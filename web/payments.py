import os, json, base64, requests
from flask import Blueprint, render_template, request, flash, jsonify
from .models import Flight
from . import db
import stripe  # pip install stripe

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")

# ---- PayPal helpers
def _paypal_base_url() -> str:
    env = os.getenv("PAYPAL_ENV", "sandbox").lower()
    return "https://api-m.paypal.com" if env == "live" else "https://api-m.sandbox.paypal.com"

def _paypal_token() -> str:
    cid = os.getenv("PAYPAL_CLIENT_ID")
    sec = os.getenv("PAYPAL_SECRET")
    if not cid or not sec:
        raise RuntimeError("PAYPAL_CLIENT_ID / PAYPAL_SECRET not set")
    auth = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    r = requests.post(
        _paypal_base_url() + "/v1/oauth2/token",
        headers={"Authorization": f"Basic {auth}"},
        data={"grant_type": "client_credentials"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]

# ---- Stripe helpers
def _stripe_enabled() -> bool:
    secret = os.getenv("STRIPE_SECRET_KEY")
    pub = os.getenv("STRIPE_PUBLISHABLE_KEY")
    if not (secret and pub):
        return False
    stripe.api_key = secret
    return True

def _stripe_pub() -> str:
    return os.getenv("STRIPE_PUBLISHABLE_KEY", "")

# ---- Page
@payments_bp.route("/", methods=["GET"])
def payments_page():
    flight_id = request.args.get("flight_id", type=int)
    flight = Flight.query.get_or_404(flight_id)
    card_enabled = _stripe_enabled()
    return render_template(
        "payments.html",
        flight=flight,
        paypal_client_id=os.getenv("PAYPAL_CLIENT_ID", ""),
        stripe_publishable_key=_stripe_pub() if card_enabled else "",
        card_enabled=card_enabled,
    )

# ---- PayPal endpoints
@payments_bp.route("/create-order", methods=["POST"])
def create_order():
    flight_id = request.args.get("flight_id", type=int)
    if not flight_id and request.is_json:
        flight_id = (request.get_json(silent=True) or {}).get("flight_id")
    flight = Flight.query.get_or_404(flight_id)

    access = _paypal_token()
    body = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "CAD", "value": f"{flight.price_cents/100:.2f}"},
            "description": f"Flight {flight.origin}->{flight.destination} #{flight.id}"
        }]
    }
    r = requests.post(
        _paypal_base_url() + "/v2/checkout/orders",
        headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
        data=json.dumps(body),
        timeout=15,
    )
    r.raise_for_status()
    return jsonify(r.json())

@payments_bp.route("/capture", methods=["POST"])
def capture_order():
    data = request.get_json(silent=True) or {}
    order_id = data.get("orderID")
    if not order_id:
        return jsonify({"status": "ERROR", "message": "Missing orderID"}), 400

    access = _paypal_token()
    r = requests.post(
        _paypal_base_url() + f"/v2/checkout/orders/{order_id}/capture",
        headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
        timeout=15,
    )
    if r.status_code // 100 != 2:
        return jsonify({"status": "ERROR", "message": r.text}), 400

    flash("Payment completed with PayPal.", "success")
    return jsonify({"status": "COMPLETED"})

# ---- Stripe charge (SCA-aware)
@payments_bp.route("/charge/<int:flight_id>", methods=["POST"])
def charge_card(flight_id: int):
    if not _stripe_enabled():
        return jsonify({"ok": False, "message": "Card payments not configured"}), 400

    flight = Flight.query.get_or_404(flight_id)
    payload = request.get_json(silent=True) or {}
    pm_id = payload.get("payment_method")
    if not pm_id:
        return jsonify({"ok": False, "message": "Missing payment method"}), 400

    intent = stripe.PaymentIntent.create(
        amount=flight.price_cents,
        currency="cad",
        payment_method=pm_id,
        confirmation_method="automatic",
        confirm=True,
        description=f"Flight {flight.origin}->{flight.destination} #{flight.id}",
    )

    if intent.status == "succeeded":
        flash("Card payment completed.", "success")
        return jsonify({"ok": True})

    if intent.status == "requires_action" and intent.next_action and intent.next_action.get("type") == "use_stripe_sdk":
        return jsonify({"ok": False, "requires_action": True, "client_secret": intent.client_secret})

    return jsonify({"ok": False, "message": f"Payment status: {intent.status}"}), 400