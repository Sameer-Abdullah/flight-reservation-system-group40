from flask import Blueprint, render_template
from flask_login import login_required, current_user

account_bp = Blueprint("account", __name__)

@account_bp.get("/account")
@login_required
def account_page():
    return render_template("account.html", user=current_user)