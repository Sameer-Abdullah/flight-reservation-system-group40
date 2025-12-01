from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from urllib.parse import urlparse, urljoin
from .models import User
from . import db

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# guard helper for redirect targets so we only follow local urls
def is_safe_url(target: str) -> bool:
    """Only allow local redirects."""
    host_url = urlparse(request.host_url)
    redirect_url = urlparse(urljoin(request.host_url, target))
    return redirect_url.scheme in ("http", "https") and host_url.netloc == redirect_url.netloc


# login view: validate credentials, log user in, and redirect based on role / next param
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")

        # success
        login_user(user)
        flash("Logged in successfully.", "success")

        # staff → staff dashboard
        if user.is_staff:
            return redirect(url_for("staff_dashboard.dashboard"))

        # normal users: respect ?next= if present
        next_page = request.args.get("next")
        if next_page and is_safe_url(next_page):
            return redirect(next_page)

        # otherwise send to normal search page
        return redirect(url_for("search.search"))
    return render_template("login.html")


# registration view: basic signup flow with duplicate / staff-domain checks
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        pwd = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""

        # block staff-domain signup
        if email.endswith("@skywing.com"):
            flash("Staff accounts are created by SkyWing admin. Please use a personal email.", "warning")
            return render_template("register.html")

        if pwd != confirm:
            flash("Passwords do not match.", "warning")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "warning")
            return render_template("register.html")

        user = User(email=email)
        user.set_password(pwd)
        db.session.add(user)
        db.session.commit()
        flash("Account created. Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html")


# logout view: end the current session and send user back to home
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("home"))