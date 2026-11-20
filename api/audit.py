import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from models import AuditEvent

GENESIS = "0" * 64


def compute_hash(prev_hash, created_at, actor, action, payload):
    data = json.dumps(
        [prev_hash, created_at, actor, action, payload],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def append_event(db: Session, actor: str, action: str, payload: dict) -> AuditEvent:
    # Verrou : deux écritures simultanées ne peuvent pas prendre le même maillon
    db.execute(text("SELECT pg_advisory_xact_lock(4242)"))
    last = db.scalars(
        select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)
    ).first()
    prev_hash = last.event_hash if last else GENESIS
    created_at = datetime.now(timezone.utc).isoformat()
    payload_txt = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    event = AuditEvent(
        created_at=created_at,
        actor=actor,
        action=action,
        payload=payload_txt,
        prev_hash=prev_hash,
        event_hash=compute_hash(prev_hash, created_at, actor, action, payload_txt),
    )
    db.add(event)
    db.flush()
    return event


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    checked = 0
    for e in db.scalars(select(AuditEvent).order_by(AuditEvent.id)):
        expected = compute_hash(prev, e.created_at, e.actor, e.action, e.payload)
        if e.prev_hash != prev or e.event_hash != expected:
            return {"valid": False, "checked": checked, "broken_at_id": e.id}
        prev = e.event_hash
        checked += 1
    return {"valid": True, "checked": checked, "broken_at_id": None}