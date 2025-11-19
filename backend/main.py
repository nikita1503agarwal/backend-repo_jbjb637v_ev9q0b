from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

from database import create_document, get_documents
from schemas import Clip

app = FastAPI(title="Social Clips API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ClipCreate(Clip):
    pass


class ClipsResponse(BaseModel):
    items: List[Clip]


@app.get("/test")
async def test():
    # Verify DB connectivity by fetching first 1 document
    items = await get_documents("clip", {}, 1)
    return {"status": "ok", "count": len(items)}


@app.get("/clips", response_model=ClipsResponse)
async def list_clips(limit: int = 20):
    items = await get_documents("clip", {}, limit)
    # Pydantic model compatibility: ensure keys present
    parsed = []
    for it in items:
        try:
            parsed.append(Clip(**it))
        except Exception:
            # Skip invalid docs
            continue
    return {"items": parsed}


@app.post("/clips", response_model=Clip, status_code=201)
async def create_clip(payload: ClipCreate):
    doc = await create_document("clip", payload.model_dump())
    if not doc:
        raise HTTPException(status_code=500, detail="Failed to create clip")
    return Clip(**doc)
