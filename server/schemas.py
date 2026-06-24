"""Pydantic schemas for the OpenHer server API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """REST API chat request."""
    message: str
    persona_id: str
    session_id: Optional[str] = None
    user_name: Optional[str] = None
    client_id: Optional[str] = None


class PersonaInfo(BaseModel):
    """Persona info response."""
    persona_id: str
    name: str
    name_zh: Optional[str] = None
    age: Optional[int]
    gender: str
    mbti: Optional[str]
    tags: list[str]
    tags_zh: list[str] = []
    description: str
    avatar_url: Optional[str] = None
    has_front: bool = False
    has_awakening_video: bool = False

