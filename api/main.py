import json

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from audit import append_event, verify_chain
from db import Base, SessionLocal, engine
from models import AuditEvent

Base.metadata.create_all(engine)
app = FastAPI(title="Agent Guard")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class EventIn(BaseModel):
    actor: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=200)
    payload: dict = {}


def to_dict(e: AuditEvent) -> dict:
    return {
        "id": e.id,
        "created_at": e.created_at,
        "actor": e.actor,
        "action": e.action,
        "payload": json.loads(e.payload),
        "prev_hash": e.prev_hash,
        "event_hash": e.event_hash,
    }


@app.post("/events", status_code=201)
def create_event(body: EventIn, db: Session = Depends(get_db)):
    return to_dict(append_event(db, body.actor, body.action, body.payload))


@app.get("/events")
def list_events(db: Session = Depends(get_db)):
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.id))
    return [to_dict(e) for e in events]


@app.get("/audit/verify")
def verify(db: Session = Depends(get_db)):
    return verify_chain(db)