import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from models import AuditEvent

GENESIS = "0" * 64
CHECKPOINTS = Path(__file__).resolve().parent.parent / "anchors" / "checkpoints.jsonl"


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


def _signing_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(
        bytes.fromhex(os.environ["ANCHOR_PRIVATE_KEY"])
    )


def _message(cp: dict) -> bytes:
    return json.dumps(
        [cp["created_at"], cp["sealed_by"], cp["last_id"], cp["last_hash"]],
        separators=(",", ":"),
    ).encode("utf-8")


def create_checkpoint(db: Session, sealed_by: str) -> dict:
    last = db.scalars(
        select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1)
    ).first()
    if last is None:
        raise ValueError("Journal vide")
    cp = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sealed_by": sealed_by,
        "last_id": last.id,
        "last_hash": last.event_hash,
    }
    cp["signature"] = _signing_key().sign(_message(cp)).hex()
    CHECKPOINTS.parent.mkdir(exist_ok=True)
    with CHECKPOINTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(cp, ensure_ascii=False) + "\n")
    return cp


def verify_checkpoints(db: Session) -> dict:
    result = {"count": 0, "sealed_until": None, "problem_id": None}
    if not CHECKPOINTS.exists():
        return result
    public_key = _signing_key().public_key()
    for line in CHECKPOINTS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        cp = json.loads(line)
        try:
            public_key.verify(bytes.fromhex(cp["signature"]), _message(cp))
        except (InvalidSignature, KeyError, ValueError):
            result["problem_id"] = cp.get("last_id")
            return result
        event = db.get(AuditEvent, cp["last_id"])
        if event is None or event.event_hash != cp["last_hash"]:
            result["problem_id"] = cp["last_id"]
            return result
        result["count"] += 1
        result["sealed_until"] = cp["last_id"]
    return result


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    checked = 0
    for e in db.scalars(select(AuditEvent).order_by(AuditEvent.id)):
        expected = compute_hash(prev, e.created_at, e.actor, e.action, e.payload)
        if e.prev_hash != prev or e.event_hash != expected:
            return {
                "valid": False,
                "checked": checked,
                "broken_at_id": e.id,
                "cause": "chaine",
                "sealed_until": None,
            }
        prev = e.event_hash
        checked += 1
    seal = verify_checkpoints(db)
    if seal["problem_id"] is not None:
        return {
            "valid": False,
            "checked": checked,
            "broken_at_id": seal["problem_id"],
            "cause": "scelle",
            "sealed_until": None,
        }
    return {
        "valid": True,
        "checked": checked,
        "broken_at_id": None,
        "cause": None,
        "sealed_until": seal["sealed_until"],
    }