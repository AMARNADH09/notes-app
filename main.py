from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import engine, get_db

# Create all tables on startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Notes API",
    version="1.0.0",
    description="Multi-user notes service – REST backend",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

def _note_to_dict(note: models.Note) -> dict:
    return {
        "id": note.id,
        "title": note.title,
        "content": note.content,
        "tags": [t for t in note.tags.split(",") if t] if note.tags else [],
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


def _get_accessible_note(note_id: str, user: models.User, db: Session) -> models.Note:
    """Return note if user owns it or it was shared with them; else 403/404."""
    note = db.query(models.Note).filter(models.Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if note.owner_id != user.id and user not in note.shared_with:
        raise HTTPException(status_code=403, detail="Access denied")
    return note


def _require_owner(note: models.Note, user: models.User) -> None:
    if note.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can perform this action")


# ─────────────────────────────────────────
# Auth endpoints
# ─────────────────────────────────────────

@app.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: schemas.UserRegister, db: Session = Depends(get_db)):
    """Register a new user account."""
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        email=payload.email,
        hashed_password=auth.hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    return {"message": "User registered successfully"}


@app.post("/login")
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    """Authenticate and receive a JWT access token."""
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not auth.verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return {"access_token": auth.create_access_token(user.email)}


# ─────────────────────────────────────────
# Notes endpoints
# ─────────────────────────────────────────

@app.get("/notes", response_model=List[schemas.NoteResponse])
def get_notes(
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Get all notes owned by or shared with the authenticated user (paginated)."""
    owned = db.query(models.Note).filter(models.Note.owner_id == current_user.id).all()
    shared = list(current_user.shared_notes)

    # Merge & deduplicate by id
    seen = set()
    all_notes = []
    for note in owned + shared:
        if note.id not in seen:
            seen.add(note.id)
            all_notes.append(note)

    # Sort newest-first
    all_notes.sort(key=lambda n: n.updated_at, reverse=True)

    # Paginate
    start = (page - 1) * limit
    return [_note_to_dict(n) for n in all_notes[start : start + limit]]


@app.get("/notes/{id}")
def get_note(
    id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific note by ID (owner or shared user only)."""
    note = _get_accessible_note(id, current_user, db)
    return _note_to_dict(note)


@app.post("/notes", status_code=status.HTTP_201_CREATED)
def create_note(
    payload: schemas.NoteCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new note. Optionally pass tags for categorisation."""
    note = models.Note(
        title=payload.title,
        content=payload.content,
        tags=",".join(payload.tags) if payload.tags else "",
        owner_id=current_user.id,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return _note_to_dict(note)


@app.put("/notes/{id}")
def update_note(
    id: str,
    payload: schemas.NoteUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Update title, content, or tags of a note (owner only)."""
    note = _get_accessible_note(id, current_user, db)
    _require_owner(note, current_user)

    if payload.title is not None:
        note.title = payload.title
    if payload.content is not None:
        note.content = payload.content
    if payload.tags is not None:
        note.tags = ",".join(payload.tags)

    note.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(note)
    return _note_to_dict(note)


@app.delete("/notes/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a note (owner only)."""
    note = _get_accessible_note(id, current_user, db)
    _require_owner(note, current_user)
    db.delete(note)
    db.commit()


@app.post("/notes/{id}/share")
def share_note(
    id: str,
    payload: schemas.ShareNote,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Share a note with another registered user (owner only)."""
    note = _get_accessible_note(id, current_user, db)
    _require_owner(note, current_user)

    if payload.share_with_email == current_user.email:
        raise HTTPException(status_code=400, detail="Cannot share a note with yourself")

    target = db.query(models.User).filter(models.User.email == payload.share_with_email).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target in note.shared_with:
        return {"message": "Note is already shared with this user"}

    note.shared_with.append(target)
    db.commit()
    return {"message": f"Note shared successfully with {payload.share_with_email}"}


# ─────────────────────────────────────────
# Stretch goals
# ─────────────────────────────────────────

@app.get("/search")
def search_notes(
    q: str = Query(..., min_length=1, description="Keyword to search in title or content"),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Full-text search across notes accessible to the authenticated user."""
    kw = q.lower()

    owned = (
        db.query(models.Note)
        .filter(
            models.Note.owner_id == current_user.id,
        )
        .all()
    )
    shared = list(current_user.shared_notes)

    seen = set()
    results = []
    for note in owned + shared:
        if note.id in seen:
            continue
        seen.add(note.id)
        if kw in note.title.lower() or kw in note.content.lower() or kw in note.tags.lower():
            results.append(_note_to_dict(note))

    return results


# ─────────────────────────────────────────
# Custom feature: filter notes by tag
# ─────────────────────────────────────────

@app.get("/notes/tags/{tag}")
def get_notes_by_tag(
    tag: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Custom Feature – Tag Filtering.

    Returns all notes (owned + shared) that contain the specified tag.
    Tags make it easy to organise notes by topic (e.g. 'work', 'personal', 'ideas')
    without creating separate folders or notebooks. Chosen because it is the simplest
    organisational primitive that adds real value with very little overhead.
    """
    tag_lower = tag.lower()

    owned = db.query(models.Note).filter(models.Note.owner_id == current_user.id).all()
    shared = list(current_user.shared_notes)

    seen = set()
    results = []
    for note in owned + shared:
        if note.id in seen:
            continue
        seen.add(note.id)
        note_tags = [t.lower() for t in note.tags.split(",") if t]
        if tag_lower in note_tags:
            results.append(_note_to_dict(note))

    if not results:
        raise HTTPException(status_code=404, detail=f"No notes found with tag '{tag}'")
    return results


# ─────────────────────────────────────────
# Meta endpoints
# ─────────────────────────────────────────

@app.get("/about")
def about():
    return {
        "name": "SRIKAKOLAPU VEERA VENKATA AMARNADH BABU",
        "email": "srikakolapuamarnadh@gmail.com",
        "my_features": {
            "Note Tagging": (
                "Notes can carry comma-separated tags (e.g. 'work', 'ideas'). "
                "A dedicated GET /notes/tags/{tag} endpoint lets users filter "
                "their notes by topic instantly."
            ),

            "search": "Implemented full-text search for notes.",
            "pagination": "Added pagination support for large note collections."
        },
    }