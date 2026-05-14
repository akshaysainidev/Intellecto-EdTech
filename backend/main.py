"""
Intellecto FastAPI Backend
--------------------------
Main application entry point.

Endpoints:
  POST   /api/resume/upload/{user_id}  – Upload & parse a resume (PDF/DOCX)
  GET    /api/resume/{user_id}         – Fetch stored resume data
  GET    /api/resume/{user_id}/exists  – Check if resume exists
  DELETE /api/resume/{user_id}         – Delete resume data

Run with:
  uvicorn main:app --reload --port 8000

  
  cd c:\FullStack\Intelecto\Intellecto\backend
  .venv\Scripts\python -m uvicorn main:app --reload

"""

import logging 
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from routers.resume import router as resume_router

# ── Load environment variables ──────────────────────────────────────────────
load_dotenv()

# ── Logging configuration ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── FastAPI app ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="Intellecto API",
    description=(
        "Backend service for the Intellecto AI Interview Platform. "
        "Handles resume OCR extraction, AI parsing, and Firestore storage."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ── CORS ────────────────────────────────────────────────────────────────────
raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"CORS enabled for origins: {origins}")

# ── Routers ─────────────────────────────────────────────────────────────────
app.include_router(resume_router)

# ── Debug endpoint to list Gemini models ────────────────────────────────────
@app.get("/debug/models", tags=["Debug"])
async def list_available_models():
    """List all available Gemini models."""
    try:
        import google.generativeai as genai
        
        # Configure with API key from environment
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"error": "GEMINI_API_KEY not found in environment variables"}
        
        genai.configure(api_key=api_key)
        
        # List all models
        models = genai.list_models()
        model_list = []
        
        for model in models:
            if 'generateContent' in model.supported_generation_methods:
                model_list.append({
                    "name": model.name,
                    "display_name": model.display_name,
                    "supported_methods": model.supported_generation_methods
                })
        
        return {
            "available_models": model_list,
            "count": len(model_list),
            "api_key_configured": True
        }
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        return {"error": str(e)}

# ── Health check ────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "Intellecto API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}


# ── Dev server entry point ──────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Starting Intellecto API on http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, reload=True)