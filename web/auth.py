from flask import Blueprint, render_template, request, redirect, url_for

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # TODO: check user in DB later
        email = request.form.get("email")
        password = request.form.get("password")
        return redirect(url_for("home"))
    return render_template("login.html")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        pwd = request.form.get("password")
        confirm = request.form.get("confirm")
        # TODO: validate + save to DB later
        return redirect(url_for("auth.login"))
    return render_template("register.html")
