import os
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext

from pydantic import BaseModel, EmailStr

from database import db
from schemas import User

SECRET_KEY = os.getenv("SECRET_KEY", "secret-dev-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 14  # 14 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    full_name: Optional[str] = None
    photos: List[str] = []
    bio: Optional[str] = None
    gender: Optional[str] = None
    show_me: Optional[str] = None
    age_range: List[int] = []
    distance_km: int = 50
    interests: List[str] = []
    verified: bool = False


app = FastAPI(title="Dating App API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_user_by_email(email: str) -> Optional[dict]:
    if db is None:
        return None
    return db["user"].find_one({"email": email})


def get_user_by_id(user_id: str) -> Optional[dict]:
    if db is None:
        return None
    from bson import ObjectId
    return db["user"].find_one({"_id": ObjectId(user_id)})


def user_entity(doc: dict) -> UserPublic:
    return UserPublic(
        id=str(doc.get("_id")),
        email=doc.get("email"),
        full_name=doc.get("full_name"),
        photos=doc.get("photos", []),
        bio=doc.get("bio"),
        gender=doc.get("gender"),
        show_me=doc.get("show_me"),
        age_range=doc.get("age_range", [18, 35]),
        distance_km=doc.get("distance_km", 50),
        interests=doc.get("interests", []),
        verified=doc.get("verified", False),
    )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    return user


@app.get("/")
def root():
    return {"message": "Dating API ready"}


@app.post("/auth/register", response_model=UserPublic)
def register(user: UserCreate):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    existing = get_user_by_email(user.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user_doc = User(
        email=user.email,
        password_hash=get_password_hash(user.password),
        full_name=user.full_name,
    ).model_dump()
    user_doc["created_at"] = datetime.utcnow()
    user_doc["updated_at"] = datetime.utcnow()
    inserted_id = db["user"].insert_one(user_doc).inserted_id
    created = db["user"].find_one({"_id": inserted_id})
    return user_entity(created)


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


@app.post("/auth/login", response_model=Token)
def login(payload: LoginPayload):
    user = get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    access_token = create_access_token({"sub": str(user["_id"])})
    return {"access_token": access_token, "token_type": "bearer"}


class ProfileUpdate(BaseModel):
    photos: Optional[List[str]] = None
    bio: Optional[str] = None
    gender: Optional[str] = None
    show_me: Optional[str] = None
    age_range: Optional[List[int]] = None
    distance_km: Optional[int] = None
    interests: Optional[List[str]] = None


@app.get("/me", response_model=UserPublic)
async def me(user: dict = Depends(get_current_user)):
    return user_entity(user)


@app.put("/me", response_model=UserPublic)
async def update_me(payload: ProfileUpdate, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    updates["updated_at"] = datetime.utcnow()
    db["user"].update_one({"_id": user["_id"]}, {"$set": updates})
    fresh = db["user"].find_one({"_id": user["_id"]})
    return user_entity(fresh)


# Discovery: very simple filter (gender preference only for MVP)
@app.get("/discover", response_model=List[UserPublic])
async def discover(user: dict = Depends(get_current_user)):
    pref = user.get("show_me", "everyone")
    query = {}
    if pref in ("male", "female"):
        query["gender"] = pref
    docs = db["user"].find(query).limit(50)
    return [user_entity(d) for d in docs if str(d.get("_id")) != str(user["_id"])]


class LikePayload(BaseModel):
    target_user_id: str


@app.post("/like")
async def like(payload: LikePayload, user: dict = Depends(get_current_user)):
    target = get_user_by_id(payload.target_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # create like
    like_doc = {
        "liker_id": str(user["_id"]),
        "liked_id": payload.target_user_id,
        "created_at": datetime.utcnow(),
    }
    db["like"].insert_one(like_doc)

    # check for mutual like
    mutual = db["like"].find_one({
        "liker_id": payload.target_user_id,
        "liked_id": str(user["_id"]) 
    })
    match_created = None
    if mutual:
        # create a match if not already
        existing_match = db["match"].find_one({
            "$or": [
                {"user_a": str(user["_id"]), "user_b": payload.target_user_id},
                {"user_a": payload.target_user_id, "user_b": str(user["_id"])},
            ]
        })
        if not existing_match:
            match_doc = {
                "user_a": str(user["_id"]),
                "user_b": payload.target_user_id,
                "created_at": datetime.utcnow(),
            }
            db["match"].insert_one(match_doc)
            match_created = True
    return {"ok": True, "match": bool(match_created)}


@app.get("/matches")
async def matches(user: dict = Depends(get_current_user)):
    cur = db["match"].find({
        "$or": [
            {"user_a": str(user["_id"])},
            {"user_b": str(user["_id"])},
        ]
    }).sort("created_at", -1)
    results = []
    for m in cur:
        other_id = m["user_b"] if m["user_a"] == str(user["_id"]) else m["user_a"]
        other = get_user_by_id(other_id)
        results.append({
            "id": str(m["_id"]),
            "other": user_entity(other) if other else None,
            "created_at": m.get("created_at"),
        })
    return {"items": results}


class MessagePayload(BaseModel):
    match_id: str
    text: str


@app.post("/messages")
async def send_message(payload: MessagePayload, user: dict = Depends(get_current_user)):
    from bson import ObjectId
    match = db["match"].find_one({"_id": ObjectId(payload.match_id)})
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if str(user["_id"]) not in (match["user_a"], match["user_b"]):
        raise HTTPException(status_code=403, detail="Not part of this match")

    msg = {
        "match_id": payload.match_id,
        "sender_id": str(user["_id"]),
        "text": payload.text,
        "created_at": datetime.utcnow(),
    }
    db["message"].insert_one(msg)
    return {"ok": True}


@app.get("/messages/{match_id}")
async def get_messages(match_id: str, user: dict = Depends(get_current_user)):
    from bson import ObjectId
    match = db["match"].find_one({"_id": ObjectId(match_id)})
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if str(user["_id"]) not in (match["user_a"], match["user_b"]):
        raise HTTPException(status_code=403, detail="Not part of this match")

    cur = db["message"].find({"match_id": match_id}).sort("created_at", 1)
    items = [
        {
            "id": str(m["_id"]),
            "sender_id": m["sender_id"],
            "text": m.get("text"),
            "created_at": m.get("created_at"),
        }
        for m in cur
    ]
    return {"items": items}


# Simple upload stub (for now accept URLs via form field, or file upload later)
@app.post("/upload")
async def upload_image(url: Optional[str] = Form(None), file: Optional[UploadFile] = File(None), user: dict = Depends(get_current_user)):
    # In a real app, upload to S3/Cloudinary, return secure URL.
    if url:
        return {"url": url}
    if file:
        # We won't persist files here; just pretend success.
        return {"url": f"/uploads/{file.filename}"}
    raise HTTPException(status_code=400, detail="Provide url or file")


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
    }
    try:
        if db is not None:
            db.list_collection_names()
            response["database"] = "✅ Connected"
    except Exception as e:
        response["database"] = f"⚠️ {str(e)[:80]}"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
