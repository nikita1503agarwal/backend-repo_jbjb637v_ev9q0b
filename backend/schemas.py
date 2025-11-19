from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List


class Creator(BaseModel):
    username: str = Field(..., min_length=2, max_length=30)
    display_name: Optional[str] = None
    avatar_url: Optional[HttpUrl] = None


class Clip(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    video_url: HttpUrl
    cover_url: Optional[HttpUrl] = None
    creator: Creator
    likes: int = 0
    shares: int = 0
    comments_count: int = 0
    tags: List[str] = []
