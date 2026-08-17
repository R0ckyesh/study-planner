import base64
import datetime
import os
import secrets
import uuid
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
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
# Simple password gate (HTTP Basic Auth)
# Set APP_PASSWORD as an environment variable to enable it.
# Leave it unset to run with no password (e.g. while developing locally).
# ============================================================
APP_USERNAME = os.getenv("APP_USERNAME", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD")  # None = auth disabled


@app.middleware("http")
async def require_password(request: Request, call_next):
    if not APP_PASSWORD:
        return await call_next(request)

    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            username, _, password = decoded.partition(":")
        except Exception:
            username, password = "", ""
        user_ok = secrets.compare_digest(username, APP_USERNAME)
        pass_ok = secrets.compare_digest(password, APP_PASSWORD)
        if user_ok and pass_ok:
            return await call_next(request)

    return Response(
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="Study Planner"'},
        content="Authentication required",
    )

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
    return {
        "topics_completed": {str(d): c for d, c in topic_rows},
        "events_completed": {str(d): c for d, c in event_rows},
    }


# ============================================================
# Serve the frontend (same origin as the API -> one deployable service)
# ============================================================
app.mount("/", StaticFiles(directory="static", html=True), name="static")
