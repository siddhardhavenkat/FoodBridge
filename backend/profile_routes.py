"""Profile editing for restaurant, NGO, and runner accounts.

Lets a logged-in restaurant/NGO/runner update every field they filled in at
registration time (name, phone, address, GPS location). Admin accounts are
managed from the admin dashboard instead.
"""
from datetime import datetime
from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from db import mongo
from auth import login_required, ROLE_DASHBOARDS

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")


@profile_bp.route("/edit", methods=["GET", "POST"])
@login_required()
def edit():
    role = session.get("role")
    if role not in ("restaurant", "ngo", "runner"):
        flash("Profile editing is only available for restaurant, NGO, and runner accounts.", "error")
        return redirect(url_for(ROLE_DASHBOARDS.get(role, "auth.login")))

    user = mongo.db.users.find_one({"_id": ObjectId(session["user_id"])})
    if not user:
        flash("Account not found.", "error")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        name  = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()

        door_no       = request.form.get("door_no", "").strip()
        building_name = request.form.get("building_name", "").strip()
        street        = request.form.get("street", "").strip()
        area          = request.form.get("area", "").strip()
        city          = request.form.get("city", "").strip()
        state         = request.form.get("state", "").strip()
        pincode       = request.form.get("pincode", "").strip()
        landmark      = request.form.get("landmark", "").strip()
        gps_lat       = request.form.get("gps_latitude", "").strip()
        gps_lng       = request.form.get("gps_longitude", "").strip()

        if not name:
            flash("Name / organisation name is required.", "error")
            return redirect(url_for("profile.edit"))
        if not all([door_no, street, area, city, state, pincode]):
            flash("Door no, street, area, city, state, and pincode are required.", "error")
            return redirect(url_for("profile.edit"))

        parts = [p for p in [door_no, building_name, street, area, city, state, pincode] if p]
        address_text = ", ".join(parts)

        update = {
            "name": name,
            "phone": phone,
            "address": address_text,
            "address_details": {
                "door_no": door_no, "building_name": building_name,
                "street": street, "area": area, "city": city,
                "state": state, "pincode": pincode, "landmark": landmark,
            },
            "updated_at": datetime.utcnow(),
        }
        if gps_lat and gps_lng:
            update["gps_location"] = {"latitude": float(gps_lat), "longitude": float(gps_lng)}

        mongo.db.users.update_one({"_id": user["_id"]}, {"$set": update})
        session["name"] = name
        current_app.logger.info("Profile updated user_id=%s role=%s", session["user_id"], role)
        flash("Profile updated!", "success")
        return redirect(url_for("profile.edit"))

    return render_template("edit_profile.html", user=user)
