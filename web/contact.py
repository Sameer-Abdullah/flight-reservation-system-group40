from flask import Blueprint, request, render_template

general_bp = Blueprint("general", __name__)

@general_bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        email = request.form["email"]
        message = request.form["message"]

        print("CONTACT MESSAGE:", name, phone, email, message)
        return render_template("contact_us.html", success=True)

    return render_template("contact_us.html")
