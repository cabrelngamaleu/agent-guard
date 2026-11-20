import hashlib
import json
from collections import Counter
from datetime import datetime, timezone

from cryptography.hazmat.primitives import serialization
from sqlalchemy import select
from sqlalchemy.orm import Session

from audit import CHECKPOINTS, _signing_key, verify_chain
from models import ActionRequest, AuditEvent
from policy import SEUIL_AUTO, SEUIL_MAX


def build_evidence(db: Session, generated_by: str) -> dict:
    actions = list(db.scalars(select(ActionRequest).order_by(ActionRequest.id)))
    events = list(db.scalars(select(AuditEvent).order_by(AuditEvent.id)))
    checkpoints = []
    if CHECKPOINTS.exists():
        checkpoints = [
            json.loads(line)
            for line in CHECKPOINTS.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    content = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": generated_by,
        "integrity": verify_chain(db),
        "policy": {
            "seuil_approbation": SEUIL_AUTO,
            "plafond": SEUIL_MAX,
            "defaut": "refus",
        },
        "summary": {
            "total": len(actions),
            "by_status": dict(Counter(a.status for a in actions)),
            "human_decisions": sum(1 for a in actions if a.decided_by),
            "invalid_agent_outputs": sum(
                1 for e in events if e.action == "agent.sortie_invalide"
            ),
        },
        "decisions": [
            {
                "id": a.id,
                "created_at": a.created_at,
                "agent": a.agent,
                "action": a.action,
                "status": a.status,
                "reason": a.reason,
                "decided_by": a.decided_by,
                "decided_at": a.decided_at,
            }
            for a in actions
        ],
        "checkpoints": checkpoints,
        "events": [
            {
                "id": e.id,
                "created_at": e.created_at,
                "actor": e.actor,
                "action": e.action,
                "event_hash": e.event_hash,
            }
            for e in events
        ],
    }
    canonical = json.dumps(
        content, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    key = _signing_key()
    public_key = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return {
        "content": content,
        "sha256": digest,
        "signature": key.sign(bytes.fromhex(digest)).hex(),
        "public_key": public_key.hex(),
    }