"""Runner delivery workflow module."""
from datetime import datetime
from bson import ObjectId
from flask import Blueprint, render_template, redirect, url_for, flash, session, current_app, jsonify, request
from db import mongo
from auth import login_required

runner_bp = Blueprint("runner", __name__, url_prefix="/runner")


def _attach_contacts(donation):
    """Attach restaurant phone (pickup) and NGO phone + coordinates (drop-off)
    to a donation dict, Zomato/Swiggy-delivery-boy style, so the runner has
    everything needed for pickup and drop without leaving the dashboard."""
    rid = donation.get("restaurant_id")
    if rid:
        restaurant = mongo.db.users.find_one({"_id": ObjectId(rid)}) if ObjectId.is_valid(str(rid)) else None
        donation["restaurant_phone"] = restaurant.get("phone", "") if restaurant else ""

    nid = donation.get("ngo_id")
    if nid:
        ngo = mongo.db.users.find_one({"_id": ObjectId(nid)}) if ObjectId.is_valid(str(nid)) else None
        if ngo:
            donation["ngo_phone"] = ngo.get("phone", "")
            donation["ngo_address"] = ngo.get("address", "")
            gps = ngo.get("gps_location") or {}
            donation["ngo_latitude"] = gps.get("latitude")
            donation["ngo_longitude"] = gps.get("longitude")
    return donation


@runner_bp.route("/dashboard")
@login_required("runner")
def dashboard():
    # Only show jobs where NGO explicitly requested a runner
    jobs = list(mongo.db.donations.find({
        "status": "Accepted",
        "collection_type": "runner",
        "runner_id": {"$exists": False}
    }).sort("updated_at", -1))
    for d in jobs:
        _attach_contacts(d)

    my_jobs = list(mongo.db.donations.find({"runner_id": session["user_id"], "status": {"$in": ["Accepted", "Picked Up"]}}).sort("updated_at", -1))
    for d in my_jobs:
        _attach_contacts(d)

    history = list(mongo.db.donations.find({"runner_id": session["user_id"], "status": "Delivered"}).sort("updated_at", -1))
    return render_template("runner_dashboard.html", jobs=jobs, my_jobs=my_jobs, history=history)

@runner_bp.route("/accept/<donation_id>", methods=["POST"])
@login_required("runner")
def accept_delivery(donation_id):
    runner = mongo.db.users.find_one({"_id": ObjectId(session["user_id"])})
    runner_phone = runner.get("phone", "") if runner else ""
    mongo.db.donations.update_one(
        {"_id": ObjectId(donation_id), "status": "Accepted", "collection_type": "runner"},
        {"$set": {
            "runner_id": session["user_id"],
            "runner_name": session["name"],
            "runner_phone": runner_phone,
            "updated_at": datetime.utcnow()
        }}
    )
    flash("Job accepted! Get the Pickup OTP from the restaurant.", "success")
    return redirect(url_for("runner.dashboard"))

@runner_bp.route("/verify_pickup_otp/<donation_id>", methods=["POST"])
@login_required("runner")
def verify_pickup(donation_id):
    entered = str(request.form.get("otp", "")).strip()
    donation = mongo.db.donations.find_one({"_id": ObjectId(donation_id), "runner_id": session["user_id"]})
    if not donation:
        flash("Not authorized", "error")
        return redirect(url_for("runner.dashboard"))
    if entered == donation.get("pickup_otp", ""):
        mongo.db.donations.update_one(
            {"_id": ObjectId(donation_id)},
            {"$set": {"pickup_otp_verified": True, "status": "Picked Up", "updated_at": datetime.utcnow()}}
        )
        flash("Pickup confirmed! Food collected.", "success")
    else:
        flash("Wrong OTP. Ask restaurant for correct code.", "error")
    return redirect(url_for("runner.dashboard"))

@runner_bp.route("/verify_delivery_otp/<donation_id>", methods=["POST"])
@login_required("runner")
def verify_delivery(donation_id):
    entered = str(request.form.get("otp", "")).strip()
    donation = mongo.db.donations.find_one({"_id": ObjectId(donation_id), "runner_id": session["user_id"]})
    if not donation:
        flash("Not authorized", "error")
        return redirect(url_for("runner.dashboard"))
    if entered == donation.get("delivery_otp", ""):
        mongo.db.donations.update_one(
            {"_id": ObjectId(donation_id)},
            {"$set": {"delivery_otp_verified": True, "status": "Delivered", "updated_at": datetime.utcnow()}}
        )
        flash("Delivered! Great work.", "success")
    else:
        flash("Wrong OTP. Ask NGO for correct code.", "error")
    return redirect(url_for("runner.dashboard"))

@runner_bp.route("/api/location/<runner_id>")
def get_runner_location(runner_id):
    """Public API to get runner location for restaurant/NGO dashboards."""
    loc = mongo.db.locations.find_one({"user_id": runner_id}, sort=[("timestamp", -1)])
    if not loc:
        return jsonify({})
    return jsonify({"latitude": loc["latitude"], "longitude": loc["longitude"], "timestamp": loc["timestamp"].isoformat()})
