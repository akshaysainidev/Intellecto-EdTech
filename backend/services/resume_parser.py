"""
Resume parser service using Google Gemini AI.
Takes raw text extracted from a resume and returns structured data.
"""

from __future__ import annotations
import json
import logging
import os
import re
from typing import Any

import google.generativeai as genai
from dotenv import load_dotenv

from models import (
    ResumeData,
    ExperienceEntry,
    EducationEntry,
    ProjectEntry,
)

load_dotenv()

logger = logging.getLogger(__name__)

# Initialize Gemini
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logger.error("GEMINI_API_KEY not found in environment variables")
    raise ValueError("GEMINI_API_KEY is required")

genai.configure(api_key=api_key)

# Get available models at startup
AVAILABLE_MODELS = []
try:
    models = genai.list_models()
    for model in models:
        if 'generateContent' in model.supported_generation_methods:
            AVAILABLE_MODELS.append(model.name)
    logger.info(f"Available Gemini models: {AVAILABLE_MODELS}")
except Exception as e:
    logger.warning(f"Could not list models: {e}")

# Try different model name formats based on what's available
def _get_gemini_model():
    """Get a working Gemini model by trying different names."""
    
    # If we have available models from the API, try those first
    if AVAILABLE_MODELS:
        for model_name in AVAILABLE_MODELS:
            try:
                logger.info(f"Attempting to initialize model from available list: {model_name}")
                model = genai.GenerativeModel(model_name)
                logger.info(f"Successfully initialized model: {model_name}")
                return model, model_name
            except Exception as e:
                logger.warning(f"Failed to initialize {model_name}: {e}")
                continue
    
    # Fallback to common model names
    MODEL_NAMES_TO_TRY = [
        "gemini-1.5-flash",           # Latest flash model
        "gemini-1.5-pro",             # Latest pro model  
        "gemini-pro",                 # Older pro model
        "gemini-1.0-pro",            # Original pro model
        "models/gemini-1.5-flash",   # With models/ prefix
        "models/gemini-1.5-pro",     # With models/ prefix
        "models/gemini-pro",         # With models/ prefix
    ]
    
    for model_name in MODEL_NAMES_TO_TRY:
        try:
            logger.info(f"Attempting to initialize model: {model_name}")
            model = genai.GenerativeModel(model_name)
            # Try a simple test to ensure it works
            test_response = model.generate_content("test")
            logger.info(f"Successfully initialized and tested model: {model_name}")
            return model, model_name
        except Exception as e:
            logger.warning(f"Failed to initialize {model_name}: {e}")
            continue
    
    # If we get here, no model worked
    raise ValueError("No working Gemini model found. Available models: " + 
                    ", ".join(AVAILABLE_MODELS) if AVAILABLE_MODELS else "unknown")

EXTRACTION_PROMPT = """
Extract the following information from this resume and return ONLY valid JSON:

{{
  "fullName": "",
  "email": "",
  "phone": "",
  "location": "",
  "summary": "",
  "skills": [],
  "workExperience": [
    {{
      "company": "",
      "title": "",
      "location": "",
      "startDate": "",
      "endDate": "",
      "description": ""
    }}
  ],
  "education": [
    {{
      "institution": "",
      "degree": "",
      "fieldOfStudy": "",
      "startDate": "",
      "endDate": "",
      "gpa": ""
    }}
  ],
  "certifications": [],
  "languages": [],
  "projects": []
}}

Resume text:
{resume_text}

Return ONLY the JSON object, no other text or explanations.
"""

# Store the working model globally
_working_model = None
_working_model_name = None

def _configure_gemini() -> tuple[genai.GenerativeModel, str]:
    """Configure and return a working Gemini model instance."""
    global _working_model, _working_model_name
    
    if _working_model is None:
        _working_model, _working_model_name = _get_gemini_model()
    
    return _working_model, _working_model_name


def _clean_json_response(raw: str) -> str:
    """Strip markdown code fences if Gemini wraps the output."""
    # Remove ```json ... ``` wrappers
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _safe_list(data: Any, item_type: type) -> list:
    """Return a list of typed items, skipping invalid entries."""
    if not isinstance(data, list):
        return []
    result = []
    for item in data:
        try:
            if isinstance(item, dict):
                result.append(item_type(**item))
            elif isinstance(item, str) and item_type == ProjectEntry:
                # Handle string projects - convert to ProjectEntry with just the name
                result.append(ProjectEntry(name=item, description="", technologies=[], link=""))
            elif isinstance(item, str):
                result.append(item)
            else:
                logger.debug(f"Skipping item of type {type(item)}: {item}")
        except Exception as e:
            logger.debug(f"Skipping invalid item: {item}, error: {e}")
            pass
    return result


async def parse_resume_with_gemini(raw_text: str) -> ResumeData:
    """
    Send raw resume text to Gemini AI and return a structured ResumeData object.

    Args:
        raw_text: Plain text extracted from the resume PDF/DOCX

    Returns:
        ResumeData: Validated Pydantic model with extracted fields
    """
    model, model_name = _configure_gemini()
    logger.info(f"Using Gemini model: {model_name}")
    
    # Limit text length to avoid token limits
    truncated_text = raw_text[:8000]
    prompt = EXTRACTION_PROMPT.format(resume_text=truncated_text)

    logger.info(f"Sending resume text to Gemini for structured extraction (text length: {len(truncated_text)} chars)...")

    try:
        # Make sure we're using the correct API method
        response = model.generate_content(prompt)
        
        # Log response for debugging
        logger.info(f"Received response from Gemini (length: {len(response.text)} chars)")
        
        raw_json = _clean_json_response(response.text)
        
        # Debug: Log first 200 chars of cleaned JSON
        logger.debug(f"Cleaned JSON (first 200 chars): {raw_json[:200]}")
        
        data: dict = json.loads(raw_json)
        
    except json.JSONDecodeError as e:
        logger.error(f"Gemini returned invalid JSON: {e}")
        logger.error(f"Raw response (first 500 chars): {response.text[:500] if 'response' in locals() else 'No response'}")
        logger.error(f"Cleaned JSON (first 500 chars): {raw_json[:500] if 'raw_json' in locals() else 'No cleaned JSON'}")
        raise ValueError(f"AI returned malformed JSON. Please try again. Detail: {e}")
    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        # Log the full error details
        if hasattr(e, '__cause__'):
            logger.error(f"Cause: {e.__cause__}")
        raise RuntimeError(f"AI parsing failed: {e}")

    # Build validated model
    try:
        # Note: The API might return 'workExperience' or 'experience' based on the prompt
        experience_data = data.get("experience", data.get("workExperience", []))
        projects_data = data.get("projects", [])
        education_data = data.get("education", [])
        
        resume = ResumeData(
            fullName=data.get("fullName", ""),
            email=data.get("email", ""),
            phone=data.get("phone"),
            location=data.get("location"),
            summary=data.get("summary", ""),
            skills=[s for s in data.get("skills", []) if isinstance(s, str)],
            experience=_safe_list(experience_data, ExperienceEntry),
            education=_safe_list(education_data, EducationEntry),
            projects=_safe_list(projects_data, ProjectEntry),
            certifications=[c for c in data.get("certifications", []) if isinstance(c, str)],
            languages=[l for l in data.get("languages", []) if isinstance(l, str)],
        )
    except Exception as e:
        logger.error(f"Data validation failed: {e}")
        logger.error(f"Parsed data: {data}")
        raise ValueError(f"Could not validate parsed resume data: {e}")

    logger.info(
        f"Successfully parsed resume for: {resume.fullName} "
        f"({len(resume.skills)} skills, {len(resume.experience)} jobs, "
        f"{len(resume.projects)} projects)"
    )
    return resume