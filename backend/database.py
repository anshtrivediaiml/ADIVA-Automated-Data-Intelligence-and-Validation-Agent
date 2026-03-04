"""
ADIVA - MongoDB Database Module

Manages the MongoDB connection and provides helper accessors
for collections used across the application.

Connection string is read from MONGO_URI in the .env file.
Database name defaults to 'adiva' but can be overridden via MONGO_DB_NAME.
"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import config
from logger import logger

# ──────────────────────────────────────────
# Connection singleton
# ──────────────────────────────────────────

_client: MongoClient | None = None
_db = None


def get_client() -> MongoClient:
    """Return (and lazily create) the MongoClient singleton."""
    global _client
    if _client is None:
        uri = config.MONGO_URI
        if not uri:
            raise RuntimeError(
                "MONGO_URI is not set. Add it to your .env file. "
                "Example: MONGO_URI=mongodb://localhost:27017"
            )
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        # Quick connectivity sanity-check
        try:
            _client.admin.command("ping")
            logger.info("MongoDB connection established successfully")
        except ConnectionFailure as exc:
            logger.error(f"MongoDB connection failed: {exc}")
            _client = None
            raise
    return _client


def get_db():
    """Return the application database object."""
    global _db
    if _db is None:
        _db = get_client()[config.MONGO_DB_NAME]
    return _db


# ──────────────────────────────────────────
# Collection accessors
# ──────────────────────────────────────────

def users_collection():
    """Return the 'users' collection."""
    return get_db()["users"]


def extractions_collection():
    """Return the 'extractions' collection (for future use)."""
    return get_db()["extractions"]


# ──────────────────────────────────────────
# Seed default admin user
# ──────────────────────────────────────────

def seed_default_admin():
    """
    Insert the default admin user if the users collection is empty.
    This ensures the system is usable right after a fresh MongoDB setup.
    """
    from passlib.context import CryptContext

    coll = users_collection()

    if coll.count_documents({}) > 0:
        logger.info("Users collection already populated — skipping seed")
        return

    pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    default_password = "adiva@2026"

    admin = {
        "username": "anshtrivedi",
        "name": "Ansh Trivedi",
        "email": "ansh@adiva.ai",
        "role": "admin",
        "hashed_password": pwd_ctx.hash(default_password),
    }

    coll.insert_one(admin)
    # Create a unique index on email for fast lookups + uniqueness
    coll.create_index("email", unique=True)
    logger.info(f"Default admin user seeded: {admin['email']}")


# ──────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────

def close_connection():
    """Close the MongoDB client connection."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        logger.info("MongoDB connection closed")
