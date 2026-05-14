"""
Firestore CRUD service for resume/user data.
Collection: 'user_data'  Document ID: userId
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional

from firebase_config import get_db
from models import ResumeData

logger = logging.getLogger(__name__)

COLLECTION = "user_data"


def _to_firestore_dict(resume: ResumeData, user_id: str) -> dict:
    """Convert ResumeData to a Firestore-compatible dict."""
    now = datetime.now(timezone.utc)
    data = resume.model_dump(exclude_none=False)

    # Ensure required metadata fields
    data["userId"] = user_id
    data["updatedAt"] = now

    # Set uploadedAt only on first insert (handled by merge logic)
    if not data.get("uploadedAt"):
        data["uploadedAt"] = now

    # Convert nested Pydantic objects to plain dicts
    data["experience"] = [
        (e.model_dump() if hasattr(e, "model_dump") else e)
        for e in (resume.experience or [])
    ]
    data["education"] = [
        (e.model_dump() if hasattr(e, "model_dump") else e)
        for e in (resume.education or [])
    ]
    data["projects"] = [
        (p.model_dump() if hasattr(p, "model_dump") else p)
        for p in (resume.projects or [])
    ]

    return data


async def save_resume(user_id: str, resume: ResumeData) -> dict:
    """
    Save (upsert) parsed resume data to Firestore.

    Args:
        user_id: Firebase Auth user UID
        resume: Validated ResumeData model

    Returns:
        The data dict that was written to Firestore
    """
    db = get_db()
    doc_ref = db.collection(COLLECTION).document(user_id)

    # Check if document already exists to preserve uploadedAt
    existing = doc_ref.get()
    data = _to_firestore_dict(resume, user_id)

    if existing.exists:
        existing_data = existing.to_dict()
        data["uploadedAt"] = existing_data.get("uploadedAt", data["uploadedAt"])

    doc_ref.set(data, merge=True)
    logger.info(f"Saved resume data for user: {user_id}")
    return data


async def get_resume(user_id: str) -> Optional[dict]:
    """
    Fetch resume data for a user from Firestore.

    Args:
        user_id: Firebase Auth user UID

    Returns:
        Document data as dict, or None if not found
    """
    db = get_db()
    doc_ref = db.collection(COLLECTION).document(user_id)
    doc = doc_ref.get()

    if doc.exists:
        logger.info(f"Found resume data for user: {user_id}")
        return doc.to_dict()

    logger.info(f"No resume data found for user: {user_id}")
    return None


async def resume_exists(user_id: str) -> bool:
    """
    Check whether a resume document exists for the given user.

    Args:
        user_id: Firebase Auth user UID

    Returns:
        True if document exists in Firestore, False otherwise
    """
    db = get_db()
    doc_ref = db.collection(COLLECTION).document(user_id)
    doc = doc_ref.get()
    return doc.exists


async def delete_resume(user_id: str) -> bool:
    """
    Delete resume data for a user from Firestore.

    Args:
        user_id: Firebase Auth user UID

    Returns:
        True if deleted, False if document didn't exist
    """
    db = get_db()
    doc_ref = db.collection(COLLECTION).document(user_id)

    if not doc_ref.get().exists:
        return False

    doc_ref.delete()
    logger.info(f"Deleted resume data for user: {user_id}")
    return True
