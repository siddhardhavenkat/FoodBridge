"""Central logging setup for Annadhan.
Creates rotating log files and console logs for debugging and project evaluation.
"""
import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(app):
    """Configure app-wide logs for Flask, routes, DB, email, GPS, and chatbot actions."""
    log_dir = os.path.join(app.root_path, "..", "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(module)s:%(lineno)d | %(message)s"
    )

    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "annadhan.log"),
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    app.logger.handlers.clear()
    app.logger.setLevel(log_level)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)

    for logger_name in ["werkzeug", "pymongo", "flask_socketio", "engineio"]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
        if not logger.handlers:
            logger.addHandler(file_handler)

    app.logger.info("Annadhan logging initialized")
