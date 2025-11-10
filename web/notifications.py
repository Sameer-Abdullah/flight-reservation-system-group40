from flask import Blueprint, request, redirect, url_for, flash
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from twilio.rest import Client
from dotenv import load_dotenv
import os
import sqlite3

load_dotenv()

notifications_bp = Blueprint("notifications", __name__)

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE", "+10000000000")

def _db_path():
    here = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "instance"))
    os.makedirs(here, exist_ok=True)
    return os.path.join(here, "airline.db")

def save_subscriber(fullname, email, phone):
    con = sqlite3.connect(_db_path())
    cur = con.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS subscribers (id INTEGER PRIMARY KEY AUTOINCREMENT, fullname TEXT, email TEXT, phone TEXT)"
    )
    cur.execute(
        "INSERT INTO subscribers(fullname, email, phone) VALUES(?,?,?)",
        (fullname or "", email or "", phone or ""),
    )
    con.commit()
    con.close()

def send_email(to_email, subject, html):
    if not SENDGRID_API_KEY or not to_email:
        return
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        msg = Mail(from_email="no-reply@skywings.example", to_emails=to_email, subject=subject, html_content=html)
        sg.send(msg)
    except Exception:
        pass

def send_sms(to_phone, body):
    if not TWILIO_SID or not TWILIO_TOKEN or not to_phone:
        return
    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(from_=TWILIO_PHONE, to=to_phone, body=body)
    except Exception:
        pass

@notifications_bp.post("/subscribe")
def subscribe():
    fullname = request.form.get("fullname")
    email = request.form.get("email")
    phone = request.form.get("phone")
    save_subscriber(fullname, email, phone)
    send_email(email, "Booking Confirmed", f"<h3>Thanks {fullname}!</h3><p>Your booking has been confirmed.</p>")
    send_sms(phone, f"Hey {fullname}, your booking has been confirmed!")
    flash("Booking confirmed! You’ll receive updates soon.", "success")
    flight_id = request.args.get("flight_id") or request.form.get("flight_id")
    if flight_id:
        return redirect(url_for("payments.payments_page", flight_id=int(flight_id)))
    return redirect(url_for("search.search"))