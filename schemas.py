from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, field_validator


# ---------- Auth ----------

class UserRegister(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


# ---------- Notes ----------

class NoteCreate(BaseModel):
    title: str
    content: str
    tags: Optional[List[str]] = []

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v):
        if v is not None and not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip() if v else v


class NoteResponse(BaseModel):
    id: str
    title: str
    content: str
    tags: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------- Share ----------

class ShareNote(BaseModel):
    share_with_email: EmailStr
