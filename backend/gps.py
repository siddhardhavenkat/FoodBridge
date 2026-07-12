"""GPS tracking API for runners and live dashboards."""
from datetime import datetime
from flask import Blueprint, request, jsonify, session, current_app
from db import mongo
from auth import login_required

gps_bp = Blueprint("gps", __name__, url_prefix="/gps")

@gps_bp.route("/update", methods=["POST"])
@login_required()
def update_location():
    """Store latest GPS location for the logged-in user."""
    data = request.get_json() or {}
    record = {
        "user_id": session["user_id"],
        "role": session.get("role"),
        "latitude": float(data.get("latitude", 0)),
        "longitude": float(data.get("longitude", 0)),
        "timestamp": datetime.utcnow(),
    }
    mongo.db.locations.insert_one(record)
    current_app.logger.info("GPS updated user_id=%s role=%s lat=%s lng=%s", session.get("user_id"), session.get("role"), record["latitude"], record["longitude"])
    return jsonify({"ok": True})

@gps_bp.route("/latest/<user_id>")
@login_required()
def latest_location(user_id):
    """Return latest location for a user."""
    loc = mongo.db.locations.find_one({"user_id": user_id}, sort=[("timestamp", -1)])
    if not loc:
        return jsonify({})
    return jsonify({"latitude": loc["latitude"], "longitude": loc["longitude"], "timestamp": loc["timestamp"].isoformat()})
