"""
ADIVA - MongoDB Database Module

Manages the MongoDB connection and provides helper accessors
for collections used across the application.

Connection string is read from MONGO_URI in the .env file.
Database name defaults to 'adiva' but can be overridden via MONGO_DB_NAME.
"""

from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure
from datetime import datetime
from typing import Any, Dict, Optional, List
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
    """Return the 'extractions' collection."""
    return get_db()["extractions"]


def validations_collection():
    """Return the 'validations' collection (audit reports)."""
    return get_db()["validations"]


# ──────────────────────────────────────────
# Extraction storage helpers
# ──────────────────────────────────────────

def store_extraction(extraction_id: str, data: Dict[str, Any]) -> str:
    """
    Upsert an extraction result into MongoDB.

    Args:
        extraction_id: The unique folder-name ID (e.g. 20260304_105036_resume)
        data: The full extraction result dict

    Returns:
        The extraction_id
    """
    try:
        coll = extractions_collection()

        doc = {
            **data,
            "extraction_id": extraction_id,
            "stored_at": datetime.utcnow().isoformat(),
        }

        # Remove fields that can't be stored in MongoDB (Path objects, etc.)
        doc.pop("output_file", None)
        doc.pop("extraction_folder", None)
        doc.pop("exports", None)

        coll.update_one(
            {"extraction_id": extraction_id},
            {"$set": doc},
            upsert=True,
        )

        # Ensure index exists for fast lookups
        coll.create_index("extraction_id", unique=True)
        coll.create_index([("stored_at", DESCENDING)])

        logger.info(f"Extraction stored in MongoDB: {extraction_id}")
        return extraction_id

    except Exception as exc:
        logger.error(f"Failed to store extraction in MongoDB: {exc}")
        raise


def get_extraction_from_db(extraction_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve an extraction result from MongoDB by its ID."""
    try:
        coll = extractions_collection()
        doc = coll.find_one(
            {"extraction_id": extraction_id},
            {"_id": 0},  # exclude Mongo _id
        )
        return doc
    except Exception as exc:
        logger.error(f"Failed to fetch extraction from MongoDB: {exc}")
        return None


def list_extractions_from_db(
    page: int = 1,
    page_size: int = 20,
    document_type: Optional[str] = None,
) -> Dict[str, Any]:
    """List extractions from MongoDB with pagination and optional type filter."""
    try:
        coll = extractions_collection()
        query: dict = {}
        if document_type:
            query["classification.document_type"] = document_type

        total = coll.count_documents(query)
        skip = (page - 1) * page_size
        cursor = (
            coll.find(query, {"_id": 0})
            .sort("stored_at", DESCENDING)
            .skip(skip)
            .limit(page_size)
        )

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "extractions": list(cursor),
        }
    except Exception as exc:
        logger.error(f"Failed to list extractions from MongoDB: {exc}")
        return {"total": 0, "page": page, "page_size": page_size, "extractions": []}


# ──────────────────────────────────────────
# Validation storage helpers
# ──────────────────────────────────────────

def store_validation(extraction_id: str, report_data: Dict[str, Any]) -> str:
    """
    Upsert a validation audit report into MongoDB.

    The report is linked to its source extraction via `extraction_id`.
    If the validation was for a standalone file, extraction_id may be
    a generated identifier.

    Args:
        extraction_id: Linked extraction ID (or file-based ID)
        report_data: The full AuditReport dict

    Returns:
        The extraction_id used as the key
    """
    try:
        coll = validations_collection()

        doc = {
            **report_data,
            "extraction_id": extraction_id,
            "validated_at": datetime.utcnow().isoformat(),
        }

        coll.update_one(
            {"extraction_id": extraction_id},
            {"$set": doc},
            upsert=True,
        )

        # Ensure indexes
        coll.create_index("extraction_id", unique=True)
        coll.create_index([("validated_at", DESCENDING)])

        logger.info(f"Validation stored in MongoDB: {extraction_id}")
        return extraction_id

    except Exception as exc:
        logger.error(f"Failed to store validation in MongoDB: {exc}")
        raise


def get_validation_from_db(extraction_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a validation audit report from MongoDB by extraction ID."""
    try:
        coll = validations_collection()
        doc = coll.find_one(
            {"extraction_id": extraction_id},
            {"_id": 0},
        )
        return doc
    except Exception as exc:
        logger.error(f"Failed to fetch validation from MongoDB: {exc}")
        return None


def list_validations_from_db(
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """List validation reports from MongoDB with pagination."""
    try:
        coll = validations_collection()
        total = coll.count_documents({})
        skip = (page - 1) * page_size
        cursor = (
            coll.find({}, {"_id": 0})
            .sort("validated_at", DESCENDING)
            .skip(skip)
            .limit(page_size)
        )

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "reports": list(cursor),
        }
    except Exception as exc:
        logger.error(f"Failed to list validations from MongoDB: {exc}")
        return {"total": 0, "page": page, "page_size": page_size, "reports": []}


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

