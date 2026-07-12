"""OTP generation and verification module (replaces QR codes)."""
import random
import string
from datetime import datetime, timedelta
from bson import ObjectId
from flask import Blueprint, jsonify, request, session, current_app
from db import mongo
from auth import login_required

otp_bp = Blueprint("otp", __name__, url_prefix="/otp")


def generate_otp(length=6):
    """Generate a numeric-only OTP."""
    return "".join(random.choices(string.digits, k=length))


def create_pickup_otp(donation_id):
    """Generate and store pickup OTP (given by restaurant to runner/NGO)."""
    otp = generate_otp(6)
    mongo.db.donations.update_one(
        {"_id": ObjectId(donation_id)},
        {"$set": {"pickup_otp": otp, "pickup_otp_verified": False, "pickup_otp_created_at": datetime.utcnow()}}
    )
    return otp


def create_delivery_otp(donation_id):
    """Generate and store delivery OTP (given by NGO to runner at delivery)."""
    otp = generate_otp(6)
    mongo.db.donations.update_one(
        {"_id": ObjectId(donation_id)},
        {"$set": {"delivery_otp": otp, "delivery_otp_verified": False, "delivery_otp_created_at": datetime.utcnow()}}
    )
    return otp


@otp_bp.route("/pickup/verify/<donation_id>", methods=["POST"])
@login_required()
def verify_pickup_otp(donation_id):
    """Runner/NGO submits pickup OTP received from restaurant."""
    data = request.get_json() or {}
    entered = str(data.get("otp", "")).strip()
    donation = mongo.db.donations.find_one({"_id": ObjectId(donation_id)})
    if not donation:
        return jsonify({"ok": False, "message": "Donation not found"}), 404
    stored = donation.get("pickup_otp", "")
    if entered == stored:
        mongo.db.donations.update_one(
            {"_id": ObjectId(donation_id)},
            {"$set": {"pickup_otp_verified": True, "status": "Picked Up", "updated_at": datetime.utcnow()}}
        )
        current_app.logger.info("Pickup OTP verified donation_id=%s by=%s", donation_id, session.get("user_id"))
        return jsonify({"ok": True, "message": "Pickup confirmed!"})
    return jsonify({"ok": False, "message": "Incorrect OTP. Please check with the restaurant."})


@otp_bp.route("/delivery/verify/<donation_id>", methods=["POST"])
@login_required()
def verify_delivery_otp(donation_id):
    """Runner submits delivery OTP received from NGO."""
    data = request.get_json() or {}
    entered = str(data.get("otp", "")).strip()
    donation = mongo.db.donations.find_one({"_id": ObjectId(donation_id)})
    if not donation:
        return jsonify({"ok": False, "message": "Donation not found"}), 404
    stored = donation.get("delivery_otp", "")
    if entered == stored:
        mongo.db.donations.update_one(
            {"_id": ObjectId(donation_id)},
            {"$set": {"delivery_otp_verified": True, "status": "Delivered", "updated_at": datetime.utcnow()}}
        )
        current_app.logger.info("Delivery OTP verified donation_id=%s by runner=%s", donation_id, session.get("user_id"))
        return jsonify({"ok": True, "message": "Delivery confirmed!"})
    return jsonify({"ok": False, "message": "Incorrect OTP. Please check with the NGO."})


@otp_bp.route("/get/<donation_id>")
@login_required()
def get_otps(donation_id):
    """Return OTPs for the donation (only to authorized roles)."""
    donation = mongo.db.donations.find_one({"_id": ObjectId(donation_id)})
    if not donation:
        return jsonify({}), 404
    role = session.get("role")
    result = {}
    # Restaurant sees pickup OTP they need to share
    if role == "restaurant" and str(donation.get("restaurant_id")) == session.get("user_id"):
        result["pickup_otp"] = donation.get("pickup_otp", "")
        result["pickup_otp_verified"] = donation.get("pickup_otp_verified", False)
    # NGO sees pickup OTP (to verify runner picked up) and sets delivery OTP
    if role == "ngo" and str(donation.get("ngo_id", "")) == session.get("user_id"):
        result["pickup_otp_verified"] = donation.get("pickup_otp_verified", False)
        result["delivery_otp"] = donation.get("delivery_otp", "")
        result["delivery_otp_verified"] = donation.get("delivery_otp_verified", False)
    return jsonify(result)
