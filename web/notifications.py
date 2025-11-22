from flask import Blueprint, request, redirect, url_for, flash
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from twilio.rest import Client
from dotenv import load_dotenv
import os, sqlite3

load_dotenv()

notifications_bp = Blueprint("notifications", __name__)

# load API keys from environment
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")

# helper for local storage
def save_subscriber(fullname, email, phone):
    conn = sqlite3.connect("subscribers.db")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS subscribers (id INTEGER PRIMARY KEY AUTOINCREMENT, fullname TEXT, email TEXT, phone TEXT)"
    )
    conn.execute(
        "INSERT INTO subscribers (fullname, email, phone) VALUES (?, ?, ?)",
        (fullname, email, phone),
    )
    conn.commit()
    conn.close()

def send_email(to_email, subject, html):
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        message = Mail(
            from_email="noreply@skywings.com",
            to_emails=to_email,
            subject=subject,
            html_content=html,
        )
        sg.send(message)
    except Exception as e:
        print("Email error:", e)

def send_sms(to_phone, body):
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(from_=TWILIO_PHONE, to=to_phone, body=body)
    except Exception as e:
        print("SMS error:", e)

@notifications_bp.route("/subscribe", methods=["POST"])
def subscribe():
    fullname = request.form.get("fullname")
    email = request.form.get("email")
    phone = request.form.get("phone")
    flight_id = request.form.get("flight_id", type=int) or request.args.get("flight_id", type=int)

    save_subscriber(fullname, email, phone)
    send_email(email, "Booking Confirmed", f"<h3>Thanks {fullname}!</h3><p>Your booking has been confirmed.</p>")
    send_sms(phone, f"Hey {fullname}, your booking has been confirmed!")

    flash("Booking confirmed! You’ll receive updates soon.", "success")
    # Redirect to the payment page if we know the flight, otherwise fall back to search.
    if flight_id:
        return redirect(url_for("payments.payments_page", flight_id=flight_id))
    return redirect(url_for("search.search"))
