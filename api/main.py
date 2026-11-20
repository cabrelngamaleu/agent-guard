import json
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from audit import append_event, verify_chain
from db import Base, SessionLocal, engine
from models import ActionRequest, AuditEvent
from policy import evaluate

Base.metadata.create_all(engine)
app = FastAPI(title="Agent Guard")

STATUS = {"allow": "allowed", "require_approval": "pending", "deny": "denied"}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ActionIn(BaseModel):
    agent: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=200)
    payload: dict = {}


class DecisionIn(BaseModel):
    approver: str = Field(min_length=1, max_length=200)
    comment: str = Field(default="", max_length=300)


def event_to_dict(e: AuditEvent) -> dict:
    return {
        "id": e.id,
        "created_at": e.created_at,
        "actor": e.actor,
        "action": e.action,
        "payload": json.loads(e.payload),
        "prev_hash": e.prev_hash,
        "event_hash": e.event_hash,
    }


def action_to_dict(a: ActionRequest) -> dict:
    return {
        "id": a.id,
        "created_at": a.created_at,
        "agent": a.agent,
        "action": a.action,
        "payload": json.loads(a.payload),
        "status": a.status,
        "reason": a.reason,
        "decided_by": a.decided_by,
        "decided_at": a.decided_at,
    }


@app.post("/actions", status_code=201)
def request_action(body: ActionIn, db: Session = Depends(get_db)):
    decision, reason = evaluate(body.action, body.payload)
    req = ActionRequest(
        created_at=now(),
        agent=body.agent,
        action=body.action,
        payload=json.dumps(body.payload, sort_keys=True, ensure_ascii=False),
        status=STATUS[decision],
        reason=reason,
    )
    db.add(req)
    db.flush()
    append_event(
        db,
        body.agent,
        f"action.{STATUS[decision]}",
        {
            "request_id": req.id,
            "action": body.action,
            "payload": body.payload,
            "reason": reason,
        },
    )
    db.commit()
    return action_to_dict(req)


@app.get("/actions")
def list_actions(status: str | None = None, db: Session = Depends(get_db)):
    query = select(ActionRequest).order_by(ActionRequest.id.desc())
    if status:
        query = query.where(ActionRequest.status == status)
    return [action_to_dict(a) for a in db.scalars(query)]


def decide(request_id: int, body: DecisionIn, new_status: str, db: Session) -> dict:
    req = db.scalars(
        select(ActionRequest).where(ActionRequest.id == request_id).with_for_update()
    ).first()
    if req is None:
        raise HTTPException(404, "Demande introuvable")
    if req.status != "pending":
        raise HTTPException(409, f"Demande déjà traitée ({req.status})")
    if body.approver == req.agent:
        raise HTTPException(403, "Le demandeur ne peut pas valider sa propre demande")
    req.status = new_status
    req.decided_by = body.approver
    req.decided_at = now()
    append_event(
        db,
        body.approver,
        f"action.{new_status}",
        {"request_id": req.id, "comment": body.comment},
    )
    db.commit()
    return action_to_dict(req)


@app.post("/actions/{request_id}/approve")
def approve(request_id: int, body: DecisionIn, db: Session = Depends(get_db)):
    return decide(request_id, body, "approved", db)


@app.post("/actions/{request_id}/reject")
def reject(request_id: int, body: DecisionIn, db: Session = Depends(get_db)):
    return decide(request_id, body, "rejected", db)


@app.get("/events")
def list_events(db: Session = Depends(get_db)):
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.id))
    return [event_to_dict(e) for e in events]


@app.get("/audit/verify")
def verify(db: Session = Depends(get_db)):
    return verify_chain(db)

from agent import propose


class AgentIn(BaseModel):
    instruction: str = Field(min_length=1, max_length=1000)


@app.post("/agent/run", status_code=201)
def agent_run(body: AgentIn, db: Session = Depends(get_db)):
    try:
        proposal, mode = propose(body.instruction)
        action = ActionIn(
            agent="agent-ia",
            action=proposal["action"],
            payload=proposal.get("payload", {}),
        )
    except Exception:
        append_event(
            db, "agent-ia", "agent.sortie_invalide", {"instruction": body.instruction}
        )
        db.commit()
        raise HTTPException(502, "Sortie de l'agent invalide : aucune action transmise")
    append_event(
        db,
        "agent-ia",
        "agent.proposition",
        {"instruction": body.instruction, "mode": mode, "proposal": proposal},
    )
    return request_action(action, db)