# Notes App – Backend API

A multi-user notes service built with **FastAPI + SQLite + JWT auth**.

## Quick Start (local)

```bash
# 1. Create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the server
uvicorn main:app --reload
```

API will be live at **http://localhost:8000**  
Interactive docs at **http://localhost:8000/docs**

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `change-me-in-production-...` | JWT signing secret – **must change in prod** |
| `DATABASE_URL` | `sqlite:///./notes.db` | Any SQLAlchemy-compatible URL |

---

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/register` | ❌ | Create account |
| POST | `/login` | ❌ | Get JWT token |
| GET | `/notes` | ✅ | List all notes (paginated) |
| POST | `/notes` | ✅ | Create note |
| GET | `/notes/{id}` | ✅ | Get specific note |
| PUT | `/notes/{id}` | ✅ | Update note |
| DELETE | `/notes/{id}` | ✅ | Delete note |
| POST | `/notes/{id}/share` | ✅ | Share note with another user |
| GET | `/notes/tags/{tag}` | ✅ | **Custom** – filter by tag |
| GET | `/search?q=keyword` | ✅ | Full-text search |
| GET | `/about` | ❌ | App info |
| GET | `/openapi.json` | ❌ | OpenAPI spec |

---

## Deploy to Render (free)

1. Push this folder to a GitHub repo.
2. Go to https://render.com → **New Web Service** → connect your repo.
3. Set:
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add env var `SECRET_KEY` = some long random string.
5. Click **Deploy**.

Your base URL will look like: `https://my-notes-app.onrender.com`

---

## Custom Feature – Note Tagging

Notes accept an optional `tags` array on create/update:

```json
POST /notes
{
  "title": "Meeting notes",
  "content": "...",
  "tags": ["work", "q2"]
}
```

Filter all notes with a tag:

```
GET /notes/tags/work
Authorization: Bearer <token>
```

Tags are stored as a comma-separated string (no extra tables), making
them zero-overhead for users who don't use them and instantly useful
for those who do.
