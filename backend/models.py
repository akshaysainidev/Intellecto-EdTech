"""
Pydantic models for resume data.
These mirror the TypeScript interfaces in src/services/resumeService.ts.
"""

from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class ExperienceEntry(BaseModel):
    title: str
    company: str
    startDate: str
    endDate: Optional[str] = None
    description: str


class EducationEntry(BaseModel):
    degree: str
    institution: str
    year: str
    grade: Optional[str] = None


class ProjectEntry(BaseModel):
    name: str
    description: str = ""
    technologies: List[str] = []
    link: str = ""


class ResumeData(BaseModel):
    """Parsed resume data – mirrors the TypeScript UserData interface."""
    userId: Optional[str] = None
    fullName: str = ""
    email: str = ""
    phone: Optional[str] = None
    location: Optional[str] = None
    skills: List[str] = []
    experience: List[ExperienceEntry] = []
    education: List[EducationEntry] = []
    projects: List[ProjectEntry] = []
    certifications: List[str] = []
    languages: List[str] = []
    summary: str = ""
    resumeUrl: Optional[str] = None
    uploadedAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class ResumeUploadResponse(BaseModel):
    success: bool
    message: str
    userId: str
    resume_data: ResumeData


class ResumeExistsResponse(BaseModel):
    exists: bool
    userId: str


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None
