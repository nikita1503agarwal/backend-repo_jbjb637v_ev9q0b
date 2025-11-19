"""
Database Schemas for Dating App

Each Pydantic model represents a MongoDB collection (lowercased class name).
"""
from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime


class User(BaseModel):
    email: EmailStr
    password_hash: str
    full_name: Optional[str] = None
    gender: Optional[Literal["male", "female", "other"]] = None
    birthday: Optional[str] = Field(None, description="YYYY-MM-DD")
    photos: List[str] = Field(default_factory=list)
    bio: Optional[str] = None
    interests: List[str] = Field(default_factory=list)
    location: Optional[dict] = Field(None, description="{ lat: float, lng: float }")
    show_me: Optional[Literal["male", "female", "everyone"]] = "everyone"
    age_range: List[int] = Field(default_factory=lambda: [18, 35])
    distance_km: int = 50
    verified: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Profile(BaseModel):
    user_id: str
    username: Optional[str] = None
    job_title: Optional[str] = None
    company: Optional[str] = None
    school: Optional[str] = None
    prompts: List[dict] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Like(BaseModel):
    liker_id: str
    liked_id: str
    created_at: Optional[datetime] = None


class Match(BaseModel):
    user_a: str
    user_b: str
    created_at: Optional[datetime] = None


class Message(BaseModel):
    match_id: str
    sender_id: str
    text: Optional[str] = None
    media_url: Optional[str] = None
    created_at: Optional[datetime] = None


class Report(BaseModel):
    reporter_id: str
    reported_id: str
    reason: str
    created_at: Optional[datetime] = None
