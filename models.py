import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, Table, Text
from sqlalchemy.orm import relationship

from database import Base

# Many-to-many: notes shared with users
shared_notes = Table(
    "shared_notes",
    Base.metadata,
    Column("note_id", String, ForeignKey("notes.id", ondelete="CASCADE")),
    Column("user_id", String, ForeignKey("users.id", ondelete="CASCADE")),
)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    notes = relationship("Note", back_populates="owner", foreign_keys="Note.owner_id")
    shared_notes = relationship("Note", secondary=shared_notes, back_populates="shared_with")


class Note(Base):
    __tablename__ = "notes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(String, default="")          # comma-separated – our custom feature
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)

    owner = relationship("User", back_populates="notes", foreign_keys=[owner_id])
    shared_with = relationship("User", secondary=shared_notes, back_populates="shared_notes")
