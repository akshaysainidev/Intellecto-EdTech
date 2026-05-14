"""
Resume API router.
Handles upload, retrieval, and existence checks for resume data.
"""

from __future__ import annotations
import logging
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from models import ResumeData, ResumeUploadResponse, ResumeExistsResponse
from services.ocr_service import extract_text
from services.resume_parser import parse_resume_with_gemini
from services.firestore_service import (
    save_resume,
    get_resume,
    resume_exists,
    delete_resume,
)

router = APIRouter(prefix="/api/resume", tags=["Resume"])
logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post(
    "/upload/{user_id}",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and parse a resume file",
    description=(
        "Accepts a PDF or DOCX resume file, extracts text via OCR, "
        "parses it with Gemini AI, saves the structured data to Firestore, "
        "and returns the parsed data."
    ),
)
async def upload_resume(
    user_id: str,
    file: UploadFile = File(..., description="Resume file (PDF or DOCX, max 10 MB)"),
):
    # ── Validate file type ──────────────────────────────────────────────────
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type: '{content_type}'. "
                "Only PDF and DOCX files are accepted."
            ),
        )

    # ── Read file bytes ─────────────────────────────────────────────────────
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES // (1024*1024)} MB.",
        )

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    logger.info(
        f"Processing resume upload for user={user_id}, "
        f"file={file.filename}, size={len(file_bytes)} bytes"
    )

    # ── Step 1: Extract raw text ────────────────────────────────────────────
    try:
        raw_text = extract_text(file_bytes, content_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # ── Step 2: Parse with Gemini AI ────────────────────────────────────────
    try:
        resume_data: ResumeData = await parse_resume_with_gemini(raw_text)
        resume_data.userId = user_id
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))

    # ── Step 3: Save to Firestore ───────────────────────────────────────────
    try:
        await save_resume(user_id, resume_data)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Firestore save failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save resume data: {e}",
        )

    logger.info(f"Resume successfully processed and stored for user={user_id}")

    return ResumeUploadResponse(
        success=True,
        message="Resume uploaded, parsed, and stored successfully.",
        userId=user_id,
        resume_data=resume_data,
    )


@router.get(
    "/{user_id}/exists",
    response_model=ResumeExistsResponse,
    summary="Check if a user has uploaded a resume",
)
async def check_resume_exists(user_id: str):
    """Must be registered BEFORE /{user_id} to avoid path collision."""
    try:
        exists = await resume_exists(user_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        logger.error(f"Existence check failed for user={user_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return ResumeExistsResponse(exists=exists, userId=user_id)


@router.get(
    "/{user_id}",
    summary="Get stored resume data for a user",
    description="Fetches the parsed resume data from Firestore for the given user ID.",
)
async def get_user_resume(user_id: str):
    try:
        data = await get_resume(user_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        logger.error(f"Firestore fetch failed for user={user_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No resume found for user: {user_id}",
        )

    return JSONResponse(content=_serialize_firestore(data))


@router.delete(
    "/{user_id}",
    summary="Delete a user's resume data from Firestore",
)
async def delete_user_resume(user_id: str):
    try:
        deleted = await delete_resume(user_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        logger.error(f"Delete failed for user={user_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No resume found for user: {user_id}",
        )

    return {"success": True, "message": f"Resume data deleted for user: {user_id}"}



def _serialize_firestore(data: Any) -> Any:
    """Convert Firestore-specific types (DatetimeWithNanoseconds etc.) to JSON-safe types."""
    if isinstance(data, dict):
        return {
            key: _serialize_firestore(value)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [_serialize_firestore(item) for item in data]
    elif hasattr(data, "isoformat"):
        return data.isoformat()
    else:
        return data
