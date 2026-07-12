"""Real-time chat with Flask-SocketIO and MongoDB message history."""
from datetime import datetime
from flask import Blueprint, request, jsonify, session, current_app
from flask_socketio import SocketIO, emit, join_room
from db import mongo
from auth import login_required

socketio = SocketIO(cors_allowed_origins="*")
chat_bp = Blueprint("chat", __name__, url_prefix="/chat")

def init_socketio(app):
    """Attach SocketIO to Flask app."""
    socketio.init_app(app)
    return socketio

def room_for(a, b):
    """Deterministic private room id."""
    return "room_" + "_".join(sorted([str(a), str(b)]))

@socketio.on("join")
def on_join(data):
    """Join private chat room."""
    join_room(room_for(data["sender"], data["receiver"]))

@socketio.on("send_message")
def on_message(data):
    """Persist and broadcast real-time message."""
    msg = {
        "sender": data.get("sender"),
        "receiver": data.get("receiver"),
        "message": data.get("message"),
        "timestamp": datetime.utcnow(),
    }
    mongo.db.messages.insert_one(msg)
    current_app.logger.info("Chat message saved sender=%s receiver=%s", msg.get("sender"), msg.get("receiver"))
    msg["timestamp"] = msg["timestamp"].isoformat()
    emit("receive_message", msg, room=room_for(msg["sender"], msg["receiver"]))

@chat_bp.route("/history/<receiver_id>")
@login_required()
def history(receiver_id):
    """Return message history between current user and receiver."""
    uid = session["user_id"]
    messages = list(mongo.db.messages.find({"$or": [{"sender": uid, "receiver": receiver_id}, {"sender": receiver_id, "receiver": uid}]}).sort("timestamp", 1))
    for m in messages:
        m["_id"] = str(m["_id"])
        m["timestamp"] = m["timestamp"].isoformat()
    return jsonify(messages)
