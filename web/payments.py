from flask import Blueprint, render_template, request, redirect, url_for, flash

payments = Blueprint("payments", __name__, url_prefix="/payments")

@payments.route("/<int:flight_id>", methods=["GET"])
def payments_page(flight_id: int):
    """
    Render the payment page. No external gateways; just the same UI.
    """
    # You can fetch flight details from your DB if you want.
    # For now we pass enough to render the page.
    return render_template(
        "payments.html",
        flight_id=flight_id,
        currency_code="CAD",
    )

@payments.route("/submit-card", methods=["POST"])
def submit_card():
    """
    Fake card submission: accept posted form fields and complete instantly.
    """
    flight_id = request.form.get("flight_id", type=int)
    # You can read other fields here if you want to validate/save them.
    flash("Payment completed (card).", "success")
    # After payment, send them back to search (or booking confirmation if you have it).
    return redirect(url_for("search.search"))

@payments.route("/mock-paypal/<int:flight_id>", methods=["GET"])
def mock_paypal(flight_id: int):
    """
    Simulated PayPal flow: just flash and go back to search.
    """
    flash("Payment completed (PayPal – mock).", "success")
    return redirect(url_for("search.search"))

# Backward-compat alias so "from .payments import payments_bp" still works.
payments_bp = payments