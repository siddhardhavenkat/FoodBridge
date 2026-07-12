"""Admin dashboard and analytics module."""
from bson import ObjectId
from flask import Blueprint, render_template, jsonify, redirect, url_for, flash, request, current_app
from db import mongo
from auth import login_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

@admin_bp.route("/dashboard")
@login_required("admin")
def dashboard():
    """Render admin dashboard with stats and full registration list."""
    stats = {
        "restaurants": mongo.db.users.count_documents({"role": "restaurant"}),
        "ngos": mongo.db.users.count_documents({"role": "ngo"}),
        "runners": mongo.db.users.count_documents({"role": "runner"}),
        "donations": mongo.db.donations.count_documents({}),
        "active": mongo.db.donations.count_documents({"status": {"$in": ["Available", "Accepted", "Picked Up"]}}),
        "delivered": mongo.db.donations.count_documents({"status": "Delivered"}),
    }
    users = list(mongo.db.users.find({"role": {"$in": ["restaurant", "ngo", "runner"]}}).sort("created_at", -1))
    for u in users:
        u["_id"] = str(u["_id"])
    issues = list(mongo.db.issues.find().sort("created_at", -1))
    for i in issues:
        i["_id"] = str(i["_id"])
    return render_template("admin_dashboard.html", stats=stats, users=users, issues=issues)

@admin_bp.route("/analytics")
@login_required("admin")
def analytics():
    """Return analytics data for Chart.js and digital twin dashboard."""
    statuses = ["Available", "Accepted", "Picked Up", "Delivered"]
    data = {s: mongo.db.donations.count_documents({"status": s}) for s in statuses}
    meals = sum(int(d.get("quantity", 0) or 0) for d in mongo.db.donations.find({"status": "Delivered"}))
    return jsonify({"statuses": data, "meals_delivered": meals, "co2_reduction_kg": round(meals * 0.9, 2)})

@admin_bp.route("/heatmap-data")
@login_required("admin")
def heatmap_data():
    """Return every donation's coordinates (and food/restaurant/status) so the
    admin dashboard can plot a live rescue-zone heatmap."""
    points = []
    for d in mongo.db.donations.find(
        {"latitude": {"$exists": True, "$ne": 0}, "longitude": {"$exists": True, "$ne": 0}},
        {"latitude": 1, "longitude": 1, "food_type": 1, "restaurant_name": 1, "status": 1}
    ):
        if d.get("latitude") and d.get("longitude"):
            points.append({
                "lat": d["latitude"], "lng": d["longitude"],
                "food": d.get("food_type", ""), "restaurant": d.get("restaurant_name", ""),
                "status": d.get("status", ""),
            })
    return jsonify({"points": points})

@admin_bp.route("/users/<user_id>/delete", methods=["POST"])
@login_required("admin")
def delete_user(user_id):
    """Admin deletes a restaurant/NGO/runner registration."""
    user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if not user or user.get("role") not in ("restaurant", "ngo", "runner"):
        flash("Account not found or cannot be deleted.", "error")
        return redirect(url_for("admin.dashboard"))
    mongo.db.users.delete_one({"_id": ObjectId(user_id)})
    current_app.logger.info("Admin deleted user_id=%s role=%s email=%s", user_id, user.get("role"), user.get("email"))
    flash(f"Deleted {user.get('role')} account: {user.get('name')}.", "success")
    return redirect(url_for("admin.dashboard"))
