"""MongoDB connection helper for Annadhan."""
import os
import certifi
from flask_pymongo import PyMongo

mongo = PyMongo()


def init_db(app):
    """Initialize MongoDB with Flask app and log connection configuration safely."""
    mongo_uri = app.config.get("MONGO_URI") or os.getenv("MONGO_URI")
    if not mongo_uri:
        app.logger.error("MONGO_URI missing from .env")
        raise RuntimeError("MONGO_URI is missing. Add it in .env file.")
    if not mongo_uri.startswith(("mongodb://", "mongodb+srv://")):
        app.logger.error("Invalid MongoDB URI scheme")
        raise RuntimeError("Invalid MONGO_URI. It must start with mongodb:// or mongodb+srv://")

    app.config["MONGO_URI"] = mongo_uri

    # Atlas/SRV needs CA certificates. Local MongoDB should not force TLS.
    if mongo_uri.startswith("mongodb+srv://") or "tls=true" in mongo_uri.lower():
        mongo.init_app(app, tlsCAFile=certifi.where())
    else:
        mongo.init_app(app)

    app.logger.info("MongoDB initialized. Database object ready=%s", mongo.db is not None)
    return mongo
