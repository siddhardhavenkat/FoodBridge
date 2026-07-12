"""AI matching engine for recommending the best NGO."""
from datetime import datetime
from geopy.distance import geodesic
from db import mongo


def _safe_distance(a_lat, a_lng, b_lat, b_lng):
    """Return distance in km, with fallback for missing coordinates."""
    try:
        if not all([a_lat, a_lng, b_lat, b_lng]):
            return 999
        return geodesic((a_lat, a_lng), (b_lat, b_lng)).km
    except Exception:
        return 999


def recommend_best_ngo(donation):
    """Score NGOs by distance, capacity, quantity fit, and expiry urgency."""
    ngos = list(mongo.db.users.find({"role": "ngo"}))
    best = None
    best_score = -1
    quantity = int(donation.get("quantity", 0) or 0)

    try:
        expiry = datetime.fromisoformat(str(donation.get("expiry_time")))
        hours_left = max((expiry - datetime.utcnow()).total_seconds() / 3600, 0.1)
    except Exception:
        hours_left = 6

    for ngo in ngos:
        distance = _safe_distance(
            donation.get("latitude"), donation.get("longitude"),
            ngo.get("latitude"), ngo.get("longitude")
        )
        capacity = int(ngo.get("capacity", 100) or 100)
        distance_score = max(0, 40 - distance)
        capacity_score = min(30, capacity / max(quantity, 1) * 20)
        urgency_score = max(0, 30 - hours_left * 3)
        score = distance_score + capacity_score + urgency_score
        if score > best_score:
            best_score = score
            best = ngo

    if not best:
        return None
    return {
        "ngo_id": str(best["_id"]),
        "name": best.get("name"),
        "email": best.get("email"),
        "score": round(best_score, 2),
    }
