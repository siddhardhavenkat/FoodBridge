"""Authentication: register, login, logout, forgot/reset password."""

import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    current_app,
)

from werkzeug.security import generate_password_hash, check_password_hash

from db import mongo
from email_service import send_reset_email, send_welcome_email

auth_bp = Blueprint("auth", __name__)

ROLE_DASHBOARDS = {
    "admin": "admin.dashboard",
    "restaurant": "restaurant.dashboard",
    "ngo": "ngo.dashboard",
    "runner": "runner.dashboard",
}


def login_required(role=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Please login first", "error")
                return redirect(url_for("auth.login"))

            if role and session.get("role") != role:
                flash("Unauthorized access", "error")
                return redirect(
                    url_for(
                        ROLE_DASHBOARDS.get(
                            session.get("role"),
                            "auth.login"
                        )
                    )
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        role = request.form.get("role", "restaurant")
        phone = request.form.get("phone", "").strip()

        door_no = request.form.get("door_no", "").strip()
        building_name = request.form.get("building_name", "").strip()
        street = request.form.get("street", "").strip()
        area = request.form.get("area", "").strip()
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip()
        pincode = request.form.get("pincode", "").strip()
        landmark = request.form.get("landmark", "").strip()

        gps_lat = request.form.get("gps_latitude", "").strip()
        gps_lng = request.form.get("gps_longitude", "").strip()

        parts = [
            p
            for p in [
                door_no,
                building_name,
                street,
                area,
                city,
                state,
                pincode,
            ]
            if p
        ]

        address_text = ", ".join(parts)

        if not name or not email or not password or not confirm:
            flash("Name, email and password are required", "error")
            return redirect(url_for("auth.register"))

        if password != confirm:
            flash("Passwords do not match", "error")
            return redirect(url_for("auth.register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters", "error")
            return redirect(url_for("auth.register"))

        if not all([door_no, street, area, city, state, pincode]):
            flash(
                "Door no, street, area, city, state and pincode are required",
                "error",
            )
            return redirect(url_for("auth.register"))

        if role not in ["restaurant", "ngo", "runner"]:
            flash("Invalid role selected", "error")
            return redirect(url_for("auth.register"))

        if mongo.db.users.find_one({"email": email}):
            flash("Email already registered. Please login.", "error")
            return redirect(url_for("auth.login"))

        hashed = generate_password_hash(password)

        mongo.db.users.insert_one(
            {
                "name": name,
                "email": email,
                "password": hashed,
                "role": role,
                "phone": phone,
                "address": address_text,
                "address_details": {
                    "door_no": door_no,
                    "building_name": building_name,
                    "street": street,
                    "area": area,
                    "city": city,
                    "state": state,
                    "pincode": pincode,
                    "landmark": landmark,
                },
                "gps_location": {
                    "latitude": float(gps_lat) if gps_lat else None,
                    "longitude": float(gps_lng) if gps_lng else None,
                },
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )

        current_app.logger.info(
            "New user registered: %s role=%s",
            email,
            role,
        )

        try:
            send_welcome_email(email, name, role)
        except Exception as exc:
            current_app.logger.warning(
                "Welcome email failed for %s: %s",
                email,
                exc,
            )

        flash("Registration successful! Please login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = mongo.db.users.find_one({"email": email})

        if user and check_password_hash(user["password"], password):
            session["user_id"] = str(user["_id"])
            session["name"] = user["name"]
            session["role"] = user["role"]

            current_app.logger.info(
                "Login: %s role=%s",
                email,
                user["role"],
            )

            return redirect(url_for(ROLE_DASHBOARDS[user["role"]]))

        flash("Invalid email or password", "error")

    return render_template("login.html")


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()

        user = mongo.db.users.find_one({"email": email})

        if user:

            token = secrets.token_urlsafe(32)

            expires = datetime.utcnow() + timedelta(hours=1)

            mongo.db.password_resets.insert_one(
                {
                    "email": email,
                    "token": token,
                    "expires_at": expires,
                    "used": False,
                }
            )

            reset_link = url_for(
                "auth.reset_password",
                token=token,
                _external=True,
            )

            try:
                send_reset_email(
                    email,
                    user["name"],
                    reset_link,
                )

                current_app.logger.info(
                    "Password reset email sent to %s",
                    email,
                )

            except Exception as exc:

                current_app.logger.error(
                    "Reset email failed for %s: %s",
                    email,
                    exc,
                )

                flash(
                    "Could not send email. Check MAIL_USERNAME and MAIL_PASSWORD.",
                    "error",
                )

                return redirect(url_for("auth.forgot_password"))

        flash(
            "If that email is registered, a reset link has been sent.",
            "success",
        )

        return redirect(url_for("auth.login"))

    return render_template("forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):

    record = mongo.db.password_resets.find_one(
        {
            "token": token,
            "used": False,
            "expires_at": {"$gt": datetime.utcnow()},
        }
    )

    if not record:
        flash("Reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":

        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if password != confirm:
            flash("Passwords do not match", "error")
            return redirect(
                url_for(
                    "auth.reset_password",
                    token=token,
                )
            )

        if len(password) < 6:
            flash(
                "Password must be at least 6 characters",
                "error",
            )
            return redirect(
                url_for(
                    "auth.reset_password",
                    token=token,
                )
            )

        hashed = generate_password_hash(password)

        mongo.db.users.update_one(
            {"email": record["email"]},
            {"$set": {"password": hashed}},
        )

        mongo.db.password_resets.update_one(
            {"_id": record["_id"]},
            {"$set": {"used": True}},
        )

        flash("Password reset successful! Please login.", "success")

        return redirect(url_for("auth.login"))

    return render_template(
        "reset_password.html",
        token=token,
    )


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for("auth.login"))