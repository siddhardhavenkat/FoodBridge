"""QR generation and verification module."""
import os
from datetime import datetime
from bson import ObjectId
from flask import Blueprint, jsonify, session, current_app
import qrcode
from db import mongo
from auth import login_required

qr_bp = Blueprint("qr", __name__, url_prefix="/qr")


def generate_donation_qr(donation_id, restaurant_id, ngo_id="pending"):
    """Generate QR image for a donation and return relative file path."""
    payload = f"donation:{donation_id}|restaurant:{restaurant_id}|ngo:{ngo_id}|ts:{datetime.utcnow().isoformat()}"
    out_dir = os.path.join(current_app.root_path, "..", "static", "images", "qr")
    os.makedirs(out_dir, exist_ok=True)
    filename = f"donation_{donation_id}.png"
    filepath = os.path.join(out_dir, filename)
    qrcode.make(payload).save(filepath)
    return f"images/qr/{filename}", payload

@qr_bp.route("/verify/<donation_id>/<next_status>", methods=["POST"])
@login_required()
def verify_qr(donation_id, next_status):
    """Verify QR scan and update donation delivery status."""
    allowed = ["Picked Up", "Delivered"]
    if next_status not in allowed:
        return jsonify({"ok": False, "message": "Invalid status"}), 400
    mongo.db.donations.update_one(
        {"_id": ObjectId(donation_id)},
        {"$set": {"status": next_status, "updated_at": datetime.utcnow()}}
    )
    return jsonify({"ok": True, "status": next_status})
