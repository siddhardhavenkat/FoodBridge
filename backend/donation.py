"""Restaurant donation module."""
import os
import random
import string
from datetime import datetime, timedelta
from bson import ObjectId
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from werkzeug.utils import secure_filename
from db import mongo
from auth import login_required
from email_service import send_new_donation_email
from ai_match import recommend_best_ngo
from otp import create_pickup_otp

restaurant_bp = Blueprint("restaurant", __name__, url_prefix="/restaurant")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_order_id():
    """Generate a short, human-friendly, unique order ID like FB-7K2R9Q."""
    for _ in range(10):
        candidate = "FB-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not mongo.db.donations.find_one({"order_id": candidate}):
            return candidate
    return "FB-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

@restaurant_bp.route("/dashboard")
@login_required("restaurant")
def dashboard():
    donations = list(mongo.db.donations.find({"restaurant_id": session["user_id"]}).sort("created_at", -1))
    return render_template("restaurant_dashboard.html", donations=donations)

@restaurant_bp.route("/donate", methods=["POST"])
@login_required("restaurant")
def create_donation():
    image_path = ""
    file = request.files.get("food_image")
    if file and file.filename and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        upload_dir = os.path.join(current_app.root_path, "..", "static", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, filename))
        image_path = "uploads/" + filename

    # Primary food item
    food_items = [{
        "name": request.form.get("food_item", ""),
        "quantity": int(request.form.get("quantity", 0) or 0),
        "unit": request.form.get("unit", "portions"),
    }]
    # Extra food items from "+ Add item"
    extra_names = request.form.getlist("food_item_extra[]")
    extra_qtys = request.form.getlist("quantity_extra[]")
    extra_units = request.form.getlist("unit_extra[]")
    for n, q, u in zip(extra_names, extra_qtys, extra_units):
        if n.strip():
            food_items.append({"name": n.strip(), "quantity": int(q or 0), "unit": u or "portions"})

    # expires_in is hours as integer
    expires_hours = int(request.form.get("expires_hours", 4) or 4)
    expires_at = datetime.utcnow() + timedelta(hours=expires_hours)

    donation = {
        "order_id": generate_order_id(),
        "restaurant_id": session["user_id"],
        "restaurant_name": session["name"],
        "food_type": food_items[0]["name"],           # primary for display
        "food_items": food_items,                      # full list
        "quantity": food_items[0]["quantity"],
        "unit": food_items[0]["unit"],
        "expires_hours": expires_hours,
        "expires_at": expires_at,
        "notes": request.form.get("notes", ""),
        "location": request.form.get("location", ""),
        "latitude": float(request.form.get("latitude") or 0),
        "longitude": float(request.form.get("longitude") or 0),
        "food_image": image_path,
        "status": "Available",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = mongo.db.donations.insert_one(donation)
    donation_id = str(result.inserted_id)
    pickup_otp = create_pickup_otp(donation_id)
    current_app.logger.info("Donation created donation_id=%s pickup_otp=%s", donation_id, pickup_otp)

    recommendation = recommend_best_ngo(donation)
    if recommendation:
        mongo.db.donations.update_one({"_id": result.inserted_id}, {"$set": {"recommended_ngo": recommendation}})

    for ngo in mongo.db.users.find({"role": "ngo"}):
        try:
            send_new_donation_email(ngo["email"], donation)
        except Exception as exc:
            current_app.logger.warning("Email failed: %s", exc)

    flash("Food listing is now live!", "success")
    return redirect(url_for("restaurant.dashboard"))

@restaurant_bp.route("/update_items/<donation_id>", methods=["POST"])
@login_required("restaurant")
def update_items(donation_id):
    """Restaurant can edit ALL food items (primary + extras) while listing is still active."""
    donation = mongo.db.donations.find_one({"_id": ObjectId(donation_id), "restaurant_id": session["user_id"]})
    if not donation or donation.get("status") in ("Delivered", "Deleted"):
        flash("Cannot update this listing.", "error")
        return redirect(url_for("restaurant.dashboard"))

    # Every existing item (primary + extras) is submitted as parallel arrays
    # so nothing gets silently dropped from editing.
    names = request.form.getlist("food_item[]")
    qtys = request.form.getlist("quantity[]")
    units = request.form.getlist("unit[]")

    food_items = []
    for n, q, u in zip(names, qtys, units):
        if n.strip():
            food_items.append({"name": n.strip(), "quantity": int(q or 0), "unit": u or "portions"})

    # Newly added rows from "+ Add item" on the edit form
    extra_names = request.form.getlist("food_item_extra[]")
    extra_qtys = request.form.getlist("quantity_extra[]")
    extra_units = request.form.getlist("unit_extra[]")
    for n, q, u in zip(extra_names, extra_qtys, extra_units):
        if n.strip():
            food_items.append({"name": n.strip(), "quantity": int(q or 0), "unit": u or "portions"})

    if not food_items:
        flash("At least one food item is required.", "error")
        return redirect(url_for("restaurant.dashboard"))

    mongo.db.donations.update_one(
        {"_id": ObjectId(donation_id)},
        {"$set": {
            "food_items": food_items,
            "food_type": food_items[0]["name"],
            "quantity": food_items[0]["quantity"],
            "unit": food_items[0]["unit"],
            "updated_at": datetime.utcnow(),
        }}
    )
    flash("Listing updated!", "success")
    return redirect(url_for("restaurant.dashboard"))


@restaurant_bp.route("/delete/<donation_id>", methods=["POST"])
@login_required("restaurant")
def delete_donation(donation_id):
    """Restaurant deletes a live food listing. Once deleted it disappears from
    NGO / runner views since those only query for Available/Accepted/Picked Up."""
    donation = mongo.db.donations.find_one({"_id": ObjectId(donation_id), "restaurant_id": session["user_id"]})
    if not donation:
        flash("Listing not found.", "error")
        return redirect(url_for("restaurant.dashboard"))
    if donation.get("status") == "Delivered":
        flash("Delivered listings cannot be deleted — they stay in history.", "error")
        return redirect(url_for("restaurant.dashboard"))
    mongo.db.donations.update_one(
        {"_id": ObjectId(donation_id)},
        {"$set": {"status": "Deleted", "deleted_at": datetime.utcnow(), "updated_at": datetime.utcnow()}}
    )
    current_app.logger.info("Donation deleted donation_id=%s by restaurant=%s", donation_id, session["user_id"])
    flash("Listing deleted.", "success")
    return redirect(url_for("restaurant.dashboard"))

@restaurant_bp.route("/set_collection_type/<donation_id>", methods=["POST"])
@login_required("restaurant")
def set_collection_type(donation_id):
    """Restaurant sets whether NGO self-collects or sends runner."""
    ctype = request.form.get("collection_type", "")
    if ctype not in ["self", "runner"]:
        flash("Invalid choice.", "error")
        return redirect(url_for("restaurant.dashboard"))
    mongo.db.donations.update_one(
        {"_id": ObjectId(donation_id), "restaurant_id": session["user_id"]},
        {"$set": {"collection_type": ctype, "updated_at": datetime.utcnow()}}
    )
    flash("Collection type updated!", "success")
    return redirect(url_for("restaurant.dashboard"))

@restaurant_bp.route("/api/recommend/<donation_id>")
@login_required("restaurant")
def recommendation(donation_id):
    donation = mongo.db.donations.find_one({"_id": ObjectId(donation_id)})
    return jsonify(donation.get("recommended_ngo") if donation else {})
