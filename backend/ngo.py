"""NGO dashboard and donation acceptance module."""
from datetime import datetime, timedelta
from urllib.parse import quote
from bson import ObjectId
from flask import Blueprint, render_template, redirect, url_for, flash, session, current_app, jsonify, request
from db import mongo
from auth import login_required
from otp import create_delivery_otp

try:
    from geopy.distance import geodesic
except Exception:  # pragma: no cover
    geodesic = None

ngo_bp = Blueprint("ngo", __name__, url_prefix="/ngo")


def _distance_km(a_lat, a_lng, b_lat, b_lng):
    """Straight-line distance in km, or None if coordinates/geopy unavailable."""
    try:
        if not geodesic or not all([a_lat, a_lng, b_lat, b_lng]):
            return None
        return round(geodesic((a_lat, a_lng), (b_lat, b_lng)).km, 1)
    except Exception:
        return None


def _maps_link(lat, lng):
    """Google Maps turn-by-turn directions link to a lat/lng pair."""
    if not lat or not lng:
        return None
    return f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}"


def _maps_search_link(lat, lng, address):
    """Google Maps link to view a location — by coordinates if available, else by address text."""
    if lat and lng:
        return f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
    if address:
        return f"https://www.google.com/maps/search/?api=1&query={quote(address)}"
    return None


def _maps_embed(lat, lng, address):
    """Embeddable Google Maps iframe src (no API key required) for a location or address."""
    if lat and lng:
        return f"https://www.google.com/maps?q={lat},{lng}&output=embed"
    if address:
        return f"https://www.google.com/maps?q={quote(address)}&output=embed"
    return None


def _attach_restaurant_phone(donation):
    """Look up and attach the restaurant's phone number so NGOs can call after accepting."""
    rid = donation.get("restaurant_id")
    if not rid:
        return donation
    restaurant = mongo.db.users.find_one({"_id": ObjectId(rid)}) if ObjectId.is_valid(str(rid)) else None
    donation["restaurant_phone"] = restaurant.get("phone", "") if restaurant else ""
    return donation


@ngo_bp.route("/dashboard")
@login_required("ngo")
def dashboard():
    now = datetime.utcnow()
    ngo_user = mongo.db.users.find_one({"_id": ObjectId(session["user_id"])}) or {}
    ngo_gps = ngo_user.get("gps_location") or {}
    ngo_lat, ngo_lng = ngo_gps.get("latitude"), ngo_gps.get("longitude")

    available = list(mongo.db.donations.find({"status": "Available"}).sort("created_at", -1))
    for d in available:
        d["distance_km"] = _distance_km(ngo_lat, ngo_lng, d.get("latitude"), d.get("longitude"))
        d["maps_link"] = _maps_link(d.get("latitude"), d.get("longitude"))

    accepted = list(mongo.db.donations.find({"ngo_id": session["user_id"], "status": {"$in": ["Accepted", "Picked Up"]}}).sort("updated_at", -1))
    for d in accepted:
        _attach_restaurant_phone(d)
        d["distance_km"] = _distance_km(ngo_lat, ngo_lng, d.get("latitude"), d.get("longitude"))
        d["maps_link"] = _maps_link(d.get("latitude"), d.get("longitude"))

    history = list(mongo.db.donations.find({"ngo_id": session["user_id"], "status": "Delivered"}).sort("updated_at", -1))
    # Check for runner-requested items where no runner accepted within 10 min
    no_runner_alert = []
    for d in accepted:
        if d.get("collection_type") == "runner" and not d.get("runner_id"):
            requested_at = d.get("runner_requested_at") or d.get("updated_at")
            if requested_at and (now - requested_at).total_seconds() > 600:
                no_runner_alert.append(d)
    return render_template("ngo_dashboard.html", available=available, accepted=accepted, history=history, no_runner_alert=no_runner_alert, now=now)

@ngo_bp.route("/accept/<donation_id>", methods=["POST"])
@login_required("ngo")
def accept_donation(donation_id):
    res = mongo.db.donations.update_one(
        {"_id": ObjectId(donation_id), "status": "Available"},
        {"$set": {"status": "Accepted", "ngo_id": session["user_id"], "ngo_name": session["name"], "updated_at": datetime.utcnow()}}
    )
    if res.modified_count:
        current_app.logger.info("NGO accepted donation_id=%s ngo_id=%s", donation_id, session.get("user_id"))
        flash("Donation accepted! Choose how to collect it.", "success")
    else:
        flash("Donation no longer available.", "error")
    return redirect(url_for("ngo.dashboard"))

@ngo_bp.route("/set_collection/<donation_id>", methods=["POST"])
@login_required("ngo")
def set_collection(donation_id):
    """NGO decides: self-pickup or send runner."""
    ctype = request.form.get("collection_type", "self")
    update = {"collection_type": ctype, "updated_at": datetime.utcnow()}
    if ctype == "runner":
        update["runner_requested_at"] = datetime.utcnow()
    else:
        # Self pickup — generate delivery OTP immediately
        create_delivery_otp(donation_id)
    mongo.db.donations.update_one(
        {"_id": ObjectId(donation_id), "ngo_id": session["user_id"]},
        {"$set": update}
    )
    msg = "Runner will be assigned soon." if ctype == "runner" else "You are set to self-collect. Show your delivery OTP at the restaurant."
    flash(msg, "success")
    return redirect(url_for("ngo.dashboard"))

@ngo_bp.route("/generate_delivery_otp/<donation_id>", methods=["POST"])
@login_required("ngo")
def gen_delivery_otp(donation_id):
    donation = mongo.db.donations.find_one({"_id": ObjectId(donation_id), "ngo_id": session["user_id"]})
    if not donation:
        return jsonify({"ok": False}), 403
    otp = create_delivery_otp(donation_id)
    return jsonify({"ok": True, "otp": otp})

@ngo_bp.route("/api/runner_location/<donation_id>")
@login_required("ngo")
def runner_location(donation_id):
    donation = mongo.db.donations.find_one({"_id": ObjectId(donation_id)})
    if not donation or not donation.get("runner_id"):
        return jsonify({})
    loc = mongo.db.locations.find_one({"user_id": donation["runner_id"]}, sort=[("timestamp", -1)])
    if not loc:
        return jsonify({})
    runner = mongo.db.users.find_one({"_id": ObjectId(donation["runner_id"])})
    return jsonify({
        "latitude": loc["latitude"],
        "longitude": loc["longitude"],
        "runner_name": donation.get("runner_name", "Runner"),
        "runner_phone": runner.get("phone", "") if runner else "",
        "timestamp": loc["timestamp"].isoformat()
    })


@ngo_bp.route("/directory")
def directory():
    """Public directory of registered NGOs/Organizations.

    Anyone celebrating a birthday, wedding, or other occasion and wanting to
    donate food can browse this page (no login required) and contact an
    NGO/Organization directly using the details shown, including its
    location on Google Maps.
    """
    q = (request.args.get("q") or "").strip()
    query = {"role": "ngo"}
    if q:
        query["name"] = {"$regex": q, "$options": "i"}

    ngo_users = list(mongo.db.users.find(query).sort("name", 1))

    ngos = []
    for u in ngo_users:
        gps = u.get("gps_location") or {}
        lat, lng = gps.get("latitude"), gps.get("longitude")
        address = u.get("address", "")
        ngos.append({
            "name": u.get("name", "Unnamed NGO"),
            "phone": u.get("phone", ""),
            "email": u.get("email", ""),
            "address": address,
            "lat": lat,
            "lng": lng,
            "maps_link": _maps_search_link(lat, lng, address),
            "embed_src": _maps_embed(lat, lng, address),
        })

    return render_template("ngo_directory.html", ngos=ngos, search_query=q)
