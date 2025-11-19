from __future__ import annotations

import os
from typing import Any, Dict, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pydantic import BaseModel
from datetime import datetime


MONGO_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DATABASE_NAME", "appdb")

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URL)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    global _db
    if _db is None:
        _db = get_client()[DB_NAME]
    return _db


# Helper functions
async def create_document(collection_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    payload = {**data, "created_at": datetime.utcnow(), "updated_at": datetime.utcnow()}
    result = await db[collection_name].insert_one(payload)
    doc = await db[collection_name].find_one({"_id": result.inserted_id})
    if doc and "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc or {}


async def get_documents(collection_name: str, filter_dict: Dict[str, Any] | None = None, limit: int = 50):
    db = get_db()
    cursor = db[collection_name].find(filter_dict or {}).limit(limit)
    items = []
    async for doc in cursor:
        if doc and "_id" in doc:
            doc["id"] = str(doc.pop("_id"))
        items.append(doc)
    return items
