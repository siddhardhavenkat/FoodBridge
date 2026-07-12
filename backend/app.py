"""Annadhan application factory and server entrypoint."""

import os
from dotenv import load_dotenv
from flask import Flask, render_template

from db import init_db
from auth import auth_bp
from donation import restaurant_bp
from ngo import ngo_bp
from runner import runner_bp
from gps import gps_bp
from otp import otp_bp
from chat import chat_bp, init_socketio, socketio
from chatbot import chatbot_bp
from admin import admin_bp
from profile_routes import profile_bp
from support import support_bp
from email_service import init_mail
from logging_config import setup_logging

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static"
    )

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
    app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")
    app.config["MONGO_URI"] = os.getenv("MONGO_URI")

    setup_logging(app)
    init_db(app)
    init_mail(app)
    init_socketio(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(restaurant_bp)
    app.register_blueprint(ngo_bp)
    app.register_blueprint(runner_bp)
    app.register_blueprint(gps_bp)
    app.register_blueprint(otp_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(support_bp)

    @app.route("/")
    def index():
        return render_template("home.html")

    return app


app = create_app()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)