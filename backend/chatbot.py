"""FoodBridge live helper assistant for registration, login, donations, delivery,
GPS, order tracking, and dashboards. Works with or without login so anyone can
check what food is currently available."""
import re
from datetime import datetime
from bson import ObjectId
from flask import Blueprint, request, jsonify, session, current_app
from db import mongo

chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/bot")

ORDER_ID_RE = re.compile(r"\bFB-[A-Z0-9]{6,8}\b", re.IGNORECASE)

HELP_TOPICS = {
    "registration": (
        "Registration help: click Register, enter name/organization name, email, password, confirm password, role, phone, "
        "and full required address fields: door/flat number, street, area, city, state, and pincode. Password and confirm password must match. "
        "Use the Live Location button to capture GPS automatically."
    ),
    "login": (
        "Login help: click Login, enter your registered email and password, then the system opens your role-based dashboard. "
        "If login fails, check spelling, password, and whether you already registered."
    ),
    "restaurant": (
        "Restaurant help: after login, create a food donation with food type, quantity, preparation time, expiry time, pickup location, GPS, and image. "
        "FoodBridge notifies NGOs and generates QR verification for safe handover."
    ),
    "ngo": (
        "NGO help: login as NGO, open available donations, accept suitable food donations, coordinate with restaurant/runner, track delivery, and verify QR after receiving food."
    ),
    "runner": (
        "Runner help: login as runner, accept a delivery, use GPS navigation, update pickup and delivered status, and complete QR verification."
    ),
    "qr": "QR help: the QR code verifies the donation handoff from restaurant to runner and final delivery to NGO/orphanage.",
    "gps": "GPS help: click the live location button and allow browser location permission. FoodBridge stores GPS securely for maps and tracking.",
    "password": "Password help: password and confirm password are required, must be the same, and should contain at least 6 characters.",
    "address": "Address help: enter complete address like D/No or flat no, building name, street, area, city, district, state, pincode, and landmark. Required fields must not be empty.",
    "dashboard": "Dashboard help: FoodBridge provides separate dashboards for Admin, Restaurant, NGO, and Runner with role-specific actions, analytics, tracking, and history.",
    "about": "FoodBridge is an AI-powered food rescue platform that connects restaurants, NGOs, orphanages, and delivery runners to reduce food waste and feed people in need.",
}

class FoodBridgeHelperAgent:
    """Rule-based project helper assistant for FoodBridge users."""
    def __init__(self, db):
        self.db = db

    def safe_count(self, collection, query):
        """Return collection count without crashing the chatbot if DB is unavailable."""
        try:
            return self.db[collection].count_documents(query)
        except Exception as exc:  # pragma: no cover - runtime safety
            current_app.logger.exception("Chatbot count failed collection=%s error=%s", collection, exc)
            return None

    def order_lookup(self, raw_text):
        """If the message contains an Order ID (e.g. FB-7K2R9Q), look it up and
        report status, who's involved, and their phone numbers so any role can
        clarify doubts about a specific order without logging in."""
        match = ORDER_ID_RE.search(raw_text or "")
        if not match:
            return None
        order_id = match.group(0).upper()
        try:
            donation = self.db.donations.find_one({"order_id": order_id})
        except Exception:
            current_app.logger.exception("Chatbot order lookup failed")
            return f"I couldn't look up order {order_id} right now — please try again shortly."
        if not donation:
            return f"I couldn't find any order with ID {order_id}. Double-check the code from the restaurant/NGO/runner."

        food = donation.get("food_type", "food")
        status = donation.get("status", "Unknown")
        parts = [f"Order {order_id}: {food} — status: {status}.", f"Restaurant: {donation.get('restaurant_name','—')}."]
        rphone = self.lookup_phone(donation.get("restaurant_id"))
        if rphone:
            parts.append(f"Restaurant phone: {rphone}.")
        if donation.get("ngo_name"):
            parts.append(f"NGO: {donation.get('ngo_name')}.")
            nphone = self.lookup_phone(donation.get("ngo_id"))
            if nphone:
                parts.append(f"NGO phone: {nphone}.")
        if donation.get("runner_name"):
            parts.append(f"Runner: {donation.get('runner_name')}.")
            if donation.get("runner_phone"):
                parts.append(f"Runner phone: {donation.get('runner_phone')}.")
        return " ".join(parts)

    def lookup_phone(self, user_id):
        """Safely fetch a user's phone number by id."""
        try:
            if not user_id or not ObjectId.is_valid(str(user_id)):
                return ""
            user = self.db.users.find_one({"_id": ObjectId(user_id)})
            return user.get("phone", "") if user else ""
        except Exception:
            return ""

    def contact_lookup(self, raw_text):
        """Look up a restaurant/NGO by name mentioned in the message and return
        name, phone, and address if it's an unambiguous match."""
        for role_word, role in [("restaurant", "restaurant"), ("hotel", "restaurant"), ("ngo", "ngo"), ("orphanage", "ngo")]:
            if role_word not in raw_text.lower():
                continue
            # crude "named X" / "for X" extraction is unreliable, so instead try
            # matching any registered name that appears as a substring of the message
            try:
                candidates = list(self.db.users.find({"role": role}, {"name": 1, "phone": 1, "address": 1}))
            except Exception:
                return None
            low = raw_text.lower()
            for c in candidates:
                name = (c.get("name") or "").strip()
                if name and len(name) > 2 and name.lower() in low:
                    return f"{c.get('name')} ({role.upper()}) — phone: {c.get('phone','not on file')}, address: {c.get('address','not on file')}."
        return None

    def runner_availability(self):
        """Report total registered runners and how many are currently free
        (i.e. not on an active job right now)."""
        try:
            total = self.db.users.count_documents({"role": "runner"})
            busy_ids = self.db.donations.distinct("runner_id", {"status": {"$in": ["Accepted", "Picked Up"]}, "runner_id": {"$exists": True}})
            free = max(total - len(busy_ids), 0)
            return f"There are {total} registered runners, {free} currently free and {len(busy_ids)} on an active delivery right now."
        except Exception:
            current_app.logger.exception("Chatbot runner availability check failed")
            return "Runner availability will show once MongoDB is connected."

    def availability_answer(self):
        """Directly answer 'what food is available' with a clear Yes/No plus
        details — this must run before generic keyword topics like 'restaurant
        help', since both share the word 'food'."""
        try:
            items = list(self.db.donations.find({"status": "Available"}).sort("created_at", -1).limit(6))
            total = self.db.donations.count_documents({"status": "Available"})
        except Exception:
            current_app.logger.exception("Chatbot availability lookup failed")
            return "I can't reach the database right now to check availability — please try again shortly."
        if not items:
            return "No — there's no food available right now. Check back soon, or open the NGO Dashboard for live updates."
        lines = [f"{d.get('food_type','food')} × {d.get('quantity','?')} {d.get('unit','portions')} at {d.get('restaurant_name','a restaurant')} ({d.get('location','location not set')})" for d in items]
        more = f" ...and {total - len(items)} more." if total > len(items) else ""
        return f"Yes! {total} food listing(s) available right now: " + "; ".join(lines) + "." + more

    def general_answer(self, q):
        """Small talk and project-overview answers so the assistant feels
        conversational, not just a keyword-triggered help menu."""
        greetings = ["hi", "hello", "hey", "hii", "helo", "good morning", "good afternoon", "good evening"]
        if q in greetings or any(q.startswith(g) for g in greetings):
            return "Hey there! 👋 I'm the FoodBridge assistant. Ask me about available food, an Order ID, a restaurant/NGO/runner's contact details, or how the platform works."
        if any(w in q for w in ["thank", "thanks", "thank you", "thx"]):
            return "You're welcome! Let me know if there's anything else you'd like to check. 🙂"
        if any(w in q for w in ["who are you", "your name", "what are you"]):
            return "I'm the FoodBridge Assistant — a live helper built into the platform to answer questions for restaurants, NGOs, runners, and visitors, with or without logging in."
        if any(w in q for w in ["what can you do", "what do you do", "help me", "can you help"]):
            return ("I can: check an Order ID's status, tell you food currently available, look up a restaurant/NGO's phone or address, "
                    "tell you how many runners are free, and explain how registration, donations, delivery, GPS, and OTP verification work on FoodBridge.")
        if any(w in q for w in ["what is foodbridge", "about foodbridge", "about this project", "about the project",
                                 "what does this app do", "what is this app", "what is this platform", "tell me about foodbridge"]):
            return HELP_TOPICS["about"]
        return None

    def reply(self, text, user_id=None):
        """Generate assistant answer from user message."""
        q = (text or "").lower().strip()
        if not q:
            return "Hi, I am the FoodBridge live assistant. Ask me about registration, login, an Order ID, restaurant/NGO/runner phone numbers, available food, or how many runners are free right now."

        # Order ID takes top priority — works for restaurant, NGO, and runner alike.
        order_answer = self.order_lookup(text)
        if order_answer:
            return order_answer

        if any(word in q for word in ["how many runner", "runners available", "free runner", "runner free", "runners free"]):
            return self.runner_availability()

        # Food availability must be checked before the generic "restaurant help"
        # keyword block below, since both match on the word "food".
        if any(phrase in q for phrase in ["food available", "available food", "any food", "what food", "foods are available",
                                            "is there food", "food nearby", "nearby food", "food near me"]) or q.strip() in ["available?", "available"]:
            return self.availability_answer()

        contact_answer = self.contact_lookup(text)
        if contact_answer:
            return contact_answer

        general = self.general_answer(q)
        if general:
            return general

        if any(word in q for word in ["register", "registration", "sign up", "signup", "create account"]):
            return HELP_TOPICS["registration"]
        if any(word in q for word in ["login", "log in", "signin", "sign in"]):
            return HELP_TOPICS["login"]
        if any(word in q for word in ["password", "confirm password", "forgot"]):
            return HELP_TOPICS["password"]
        if any(word in q for word in ["address", "door", "flat", "building", "pincode", "landmark"]):
            return HELP_TOPICS["address"]
        if any(word in q for word in ["gps", "location", "map", "live location", "navigation"]):
            return HELP_TOPICS["gps"]
        if any(word in q for word in ["restaurant", "donate", "donation", "food", "meal"]):
            return HELP_TOPICS["restaurant"]
        if any(word in q for word in ["ngo", "orphanage", "accept"]):
            return HELP_TOPICS["ngo"]
        if any(word in q for word in ["runner", "delivery", "pickup", "deliver"]):
            return HELP_TOPICS["runner"]
        if "qr" in q or "scan" in q or "verify" in q:
            return HELP_TOPICS["qr"]
        if "dashboard" in q or "admin" in q or "analytics" in q or "report" in q:
            return HELP_TOPICS["dashboard"]
        if "about" in q or "annadhan" in q or "project" in q:
            return HELP_TOPICS["about"]
        if "track" in q:
            active = self.safe_count("donations", {"status": {"$in": ["Accepted", "Picked Up"]}})
            if active is None:
                return "Tracking works after MongoDB is connected. Use Track Runner from your dashboard for live GPS updates."
            return f"There are {active} active deliveries. Use Track Runner from your dashboard for live GPS."
        if "today" in q or "how many" in q:
            try:
                start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                donations = self.db.donations.find({"created_at": {"$gte": start}})
                meals = sum(int(d.get("quantity", 0) or 0) for d in donations)
                return f"FoodBridge has recorded approximately {meals} meals donated today."
            except Exception:
                current_app.logger.exception("Chatbot meals calculation failed")
                return "Meal analytics will work after MongoDB is connected."
        return (
            "I'm not totally sure about that one, but I can help with: available food right now, an Order ID, "
            "a restaurant/NGO/runner's phone or address, how many runners are free, or how registration, donations, "
            "delivery, GPS, and OTP verification work on FoodBridge. Try rephrasing, or ask me one of those!"
        )

@chatbot_bp.route("/ask", methods=["POST"])
def ask_bot():
    """Chatbot API endpoint."""
    text = (request.get_json() or {}).get("message", "")
    agent = FoodBridgeHelperAgent(mongo.db)
    reply = agent.reply(text, session.get("user_id"))
    current_app.logger.info("Chatbot query user_id=%s text=%s", session.get("user_id"), text[:80])
    return jsonify({"reply": reply})
