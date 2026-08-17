import base64
import datetime
import hashlib
import hmac
import os
import secrets
import time
import uuid
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
import schemas
from database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Study Planner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Password gate — real login page + signed session cookie.
# Set APP_PASSWORD as an environment variable to enable it.
# Leave it unset to run with no password (e.g. while developing locally).
# ============================================================
APP_USERNAME = os.getenv("APP_USERNAME", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD")  # None = auth disabled
SESSION_SECRET = os.getenv("SESSION_SECRET", hashlib.sha256((APP_PASSWORD or "dev-secret").encode()).hexdigest())
SESSION_COOKIE = "sp_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sign in &mdash; Study Planner</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:wght@600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;}
  body{
    margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
    font-family:'Inter',system-ui,sans-serif; background:#F7F3EA; color:#1E293B;
    background-image: radial-gradient(circle at 1px 1px, #E4DCC8 1px, transparent 0);
    background-size: 22px 22px;
  }
  .card{
    background:#fff; border-radius:16px; box-shadow:0 8px 24px rgba(22,50,79,0.12);
    padding:36px 32px; width:100%; max-width:360px;
  }
  h1{ font-family:'Fraunces',serif; font-size:1.5rem; margin:0 0 6px; color:#16324F; text-align:center; }
  p.sub{ text-align:center; color:#64748B; font-size:0.85rem; margin:0 0 24px; }
  label{ display:block; font-size:0.78rem; color:#64748B; margin-bottom:5px; font-weight:600; }
  input{
    width:100%; border:1.4px solid #E4DCC8; border-radius:8px; padding:11px 12px;
    font-size:0.95rem; font-family:inherit; margin-bottom:16px;
  }
  input:focus{ outline:none; border-color:#5B9BF0; }
  button{
    width:100%; background:#16324F; color:#fff; border:none; border-radius:8px;
    padding:12px; font-size:0.95rem; font-weight:600; cursor:pointer; font-family:inherit;
  }
  button:hover{ background:#1D4363; }
  .error{ background:#FDEAF4; color:#E86FAE; border-radius:8px; padding:10px 12px; font-size:0.85rem; margin-bottom:16px; text-align:center; }
</style>
</head>
<body>
  <form class="card" method="POST" action="/login">
    <h1>&#128213; Study Planner</h1>
    <p class="sub">Sign in to continue</p>
    {error_html}
    <label for="username">Username</label>
    <input type="text" id="username" name="username" autocomplete="username" autofocus required>
    <label for="password">Password</label>
    <input type="password" id="password" name="password" autocomplete="current-password" required>
    <button type="submit">Sign In</button>
  </form>
</body>
</html>
"""


def make_session_token(username: str) -> str:
    expiry = int(time.time()) + SESSION_MAX_AGE
    payload = f"{username}:{expiry}"
    signature = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def verify_session_token(token: str) -> bool:
    try:
        username, expiry, signature = token.rsplit(":", 2)
        payload = f"{username}:{expiry}"
        expected = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        if int(expiry) < time.time():
            return False
        return secrets.compare_digest(username, APP_USERNAME)
    except Exception:
        return False


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return LOGIN_PAGE.replace("{error_html}", "")


@app.middleware("http")
async def require_password(request: Request, call_next):
    if not APP_PASSWORD:
        return await call_next(request)

    path = request.url.path

    if path == "/login" and request.method == "POST":
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")
        user_ok = secrets.compare_digest(username, APP_USERNAME)
        pass_ok = secrets.compare_digest(password, APP_PASSWORD)
        if user_ok and pass_ok:
            token = make_session_token(username)
            response = RedirectResponse(url="/", status_code=303)
            # Only require HTTPS for the cookie when actually served over HTTPS
            # (e.g. Render). Over plain http:// (local testing), a Secure
            # cookie would be silently dropped by the browser and you'd get
            # stuck bouncing back to the login page.
            is_https = request.url.scheme == "https"
            response.set_cookie(
                SESSION_COOKIE, token, max_age=SESSION_MAX_AGE,
                httponly=True, samesite="lax", secure=is_https,
            )
            return response
        return HTMLResponse(
            LOGIN_PAGE.replace("{error_html}", '<div class="error">Incorrect username or password.</div>'),
            status_code=401,
        )

    if path == "/login":
        return await call_next(request)

    if path == "/logout":
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie(SESSION_COOKIE)
        return response

    token = request.cookies.get(SESSION_COOKIE)
    if token and verify_session_token(token):
        return await call_next(request)

    # Not logged in: send browsers to the login page, and API/JSON
    # callers a plain 401 so fetch() calls fail predictably.
    accepts_html = "text/html" in request.headers.get("accept", "")
    if accepts_html and not path.startswith("/api/"):
        return RedirectResponse(url="/login", status_code=303)
    return Response(status_code=401, content="Authentication required")

# ============================================================
# Planner events (calendar blocks)
# ============================================================

@app.get("/api/events", response_model=List[schemas.EventOut])
def list_events(
    start: datetime.date = Query(...),
    end: datetime.date = Query(...),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.PlannerEvent)
        .filter(models.PlannerEvent.date >= start, models.PlannerEvent.date <= end)
        .all()
    )


@app.post("/api/events", response_model=schemas.EventOut)
def create_event(payload: schemas.EventCreate, db: Session = Depends(get_db)):
    data = payload.dict()
    repeat_weekly = data.pop("repeat_weekly")
    repeat_weeks = max(1, min(data.pop("repeat_weeks"), 52))

    group_id = None
    if repeat_weekly and repeat_weeks > 1:
        group_id = str(uuid.uuid4())

    first_event = models.PlannerEvent(**data, recurrence_group_id=group_id)
    db.add(first_event)
    db.commit()
    db.refresh(first_event)

    if repeat_weekly and repeat_weeks > 1:
        for i in range(1, repeat_weeks):
            db.add(models.PlannerEvent(
                date=data["date"] + datetime.timedelta(weeks=i),
                start_hour=data["start_hour"],
                end_hour=data["end_hour"],
                label=data["label"],
                color=data["color"],
                recurrence_group_id=group_id,
            ))
        db.commit()

    return first_event


@app.put("/api/events/{event_id}", response_model=schemas.EventOut)
def update_event(event_id: int, payload: schemas.EventUpdate, db: Session = Depends(get_db)):
    event = db.get(models.PlannerEvent, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    data = payload.dict(exclude_unset=True)
    if "done" in data:
        event.completed_at = datetime.datetime.utcnow() if data["done"] else None
    for key, value in data.items():
        setattr(event, key, value)
    db.commit()
    db.refresh(event)
    return event


@app.delete("/api/events/{event_id}")
def delete_event(event_id: int, scope: str = Query("this"), db: Session = Depends(get_db)):
    event = db.get(models.PlannerEvent, event_id)
    if not event:
        raise HTTPException(404, "Event not found")
    if scope == "future" and event.recurrence_group_id:
        db.query(models.PlannerEvent).filter(
            models.PlannerEvent.recurrence_group_id == event.recurrence_group_id,
            models.PlannerEvent.date >= event.date,
        ).delete()
        db.commit()
    else:
        db.delete(event)
        db.commit()
    return {"ok": True}


# ============================================================
# Subjects and topics (syllabus tracker)
# ============================================================

@app.get("/api/subjects", response_model=List[schemas.SubjectOut])
def list_subjects(db: Session = Depends(get_db)):
    return db.query(models.Subject).all()


@app.post("/api/subjects", response_model=schemas.SubjectOut)
def create_subject(payload: schemas.SubjectCreate, db: Session = Depends(get_db)):
    subject = models.Subject(**payload.dict())
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


@app.delete("/api/subjects/{subject_id}")
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
    subject = db.get(models.Subject, subject_id)
    if not subject:
        raise HTTPException(404, "Subject not found")
    db.delete(subject)
    db.commit()
    return {"ok": True}


@app.post("/api/subjects/{subject_id}/topics", response_model=List[schemas.TopicOut])
def add_topics(subject_id: int, payload: schemas.TopicCreate, db: Session = Depends(get_db)):
    subject = db.get(models.Subject, subject_id)
    if not subject:
        raise HTTPException(404, "Subject not found")
    new_topics = []
    for line in payload.lines:
        line = line.strip()
        if not line:
            continue
        topic = models.Topic(subject_id=subject_id, text=line)
        db.add(topic)
        new_topics.append(topic)
    db.commit()
    for topic in new_topics:
        db.refresh(topic)
    return new_topics


@app.put("/api/topics/{topic_id}", response_model=schemas.TopicOut)
def update_topic(topic_id: int, done: bool, db: Session = Depends(get_db)):
    topic = db.get(models.Topic, topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")
    topic.done = done
    topic.completed_at = datetime.datetime.utcnow() if done else None
    db.commit()
    db.refresh(topic)
    return topic


@app.delete("/api/topics/{topic_id}")
def delete_topic(topic_id: int, db: Session = Depends(get_db)):
    topic = db.get(models.Topic, topic_id)
    if not topic:
        raise HTTPException(404, "Topic not found")
    db.delete(topic)
    db.commit()
    return {"ok": True}


# ============================================================
# Wish list
# ============================================================

@app.get("/api/wishes", response_model=List[schemas.WishOut])
def list_wishes(db: Session = Depends(get_db)):
    return db.query(models.Wish).order_by(models.Wish.created_at).all()


@app.post("/api/wishes", response_model=schemas.WishOut)
def create_wish(payload: schemas.WishCreate, db: Session = Depends(get_db)):
    text = payload.text.strip()
    if not text:
        raise HTTPException(400, "Wish text cannot be empty")
    wish = models.Wish(text=text)
    db.add(wish)
    db.commit()
    db.refresh(wish)
    return wish


@app.post("/api/wishes/bulk", response_model=List[schemas.WishOut])
def bulk_create_wishes(payload: schemas.WishBulkCreate, db: Session = Depends(get_db)):
    new_wishes = []
    for line in payload.lines:
        line = line.strip()
        if not line:
            continue
        wish = models.Wish(text=line)
        db.add(wish)
        new_wishes.append(wish)
    db.commit()
    for wish in new_wishes:
        db.refresh(wish)
    return new_wishes


@app.put("/api/wishes/{wish_id}", response_model=schemas.WishOut)
def update_wish(wish_id: int, done: bool, db: Session = Depends(get_db)):
    wish = db.get(models.Wish, wish_id)
    if not wish:
        raise HTTPException(404, "Wish not found")
    wish.done = done
    wish.completed_at = datetime.datetime.utcnow() if done else None
    db.commit()
    db.refresh(wish)
    return wish


@app.delete("/api/wishes/{wish_id}")
def delete_wish(wish_id: int, db: Session = Depends(get_db)):
    wish = db.get(models.Wish, wish_id)
    if not wish:
        raise HTTPException(404, "Wish not found")
    db.delete(wish)
    db.commit()
    return {"ok": True}


# ============================================================
# History (for "historical data of completed" tracking)
# ============================================================

@app.get("/api/history")
def history(days: int = 30, db: Session = Depends(get_db)):
    since = datetime.date.today() - datetime.timedelta(days=days)
    since_dt = datetime.datetime.combine(since, datetime.time.min)

    topic_rows = (
        db.query(func.date(models.Topic.completed_at).label("d"), func.count(models.Topic.id))
        .filter(models.Topic.completed_at.isnot(None))
        .filter(func.date(models.Topic.completed_at) >= since)
        .group_by("d")
        .all()
    )
    event_rows = (
        db.query(func.date(models.PlannerEvent.completed_at).label("d"), func.count(models.PlannerEvent.id))
        .filter(models.PlannerEvent.completed_at.isnot(None))
        .filter(func.date(models.PlannerEvent.completed_at) >= since)
        .group_by("d")
        .all()
    )

    # Detailed, subject-wise completed topics
    completed_topics = (
        db.query(models.Topic, models.Subject)
        .join(models.Subject, models.Topic.subject_id == models.Subject.id)
        .filter(models.Topic.completed_at.isnot(None))
        .filter(models.Topic.completed_at >= since_dt)
        .order_by(models.Topic.completed_at.desc())
        .all()
    )
    completed_events = (
        db.query(models.PlannerEvent)
        .filter(models.PlannerEvent.completed_at.isnot(None))
        .filter(models.PlannerEvent.completed_at >= since_dt)
        .order_by(models.PlannerEvent.completed_at.desc())
        .all()
    )

    return {
        "topics_completed": {str(d): c for d, c in topic_rows},
        "events_completed": {str(d): c for d, c in event_rows},
        "topics": [
            {
                "subject": subject.name,
                "subject_color": subject.color,
                "text": topic.text,
                "completed_at": topic.completed_at.isoformat(),
            }
            for topic, subject in completed_topics
        ],
        "events": [
            {
                "label": event.label,
                "color": event.color,
                "date": str(event.date),
                "start_hour": event.start_hour,
                "end_hour": event.end_hour,
                "completed_at": event.completed_at.isoformat(),
            }
            for event in completed_events
        ],
    }


# ============================================================
# Serve the frontend (same origin as the API -> one deployable service)
# ============================================================
app.mount("/", StaticFiles(directory="static", html=True), name="static")
