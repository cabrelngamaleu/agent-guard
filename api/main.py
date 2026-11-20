import json
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from agent import AgentError, propose
from audit import append_event, verify_chain
from auth import current_user, require_agent, require_approver, roles_of
from db import Base, SessionLocal, engine
from models import ActionRequest, AuditEvent
from policy import evaluate
from privacy import mask, unmask

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
    action: str = Field(min_length=1, max_length=200)
    payload: dict = {}


class DecisionIn(BaseModel):
    comment: str = Field(default="", max_length=300)


class AgentIn(BaseModel):
    instruction: str = Field(min_length=1, max_length=1000)


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


def submit_action(db: Session, agent: str, action: str, payload: dict) -> dict:
    decision, reason = evaluate(action, payload)
    req = ActionRequest(
        created_at=now(),
        agent=agent,
        action=action,
        payload=json.dumps(payload, sort_keys=True, ensure_ascii=False),
        status=STATUS[decision],
        reason=reason,
    )
    db.add(req)
    db.flush()
    append_event(
        db,
        agent,
        f"action.{STATUS[decision]}",
        {
            "request_id": req.id,
            "action": action,
            "payload": payload,
            "reason": reason,
        },
    )
    db.commit()
    return action_to_dict(req)


@app.get("/me")
def me(user: dict = Depends(current_user)):
    return {"username": user["preferred_username"], "roles": roles_of(user)}


@app.post("/actions", status_code=201)
def request_action(
    body: ActionIn,
    agent: str = Depends(require_agent),
    db: Session = Depends(get_db),
):
    return submit_action(db, agent, body.action, body.payload)


@app.get("/actions", dependencies=[Depends(current_user)])
def list_actions(status: str | None = None, db: Session = Depends(get_db)):
    query = select(ActionRequest).order_by(ActionRequest.id.desc())
    if status:
        query = query.where(ActionRequest.status == status)
    return [action_to_dict(a) for a in db.scalars(query)]


def decide(
    request_id: int, approver: str, comment: str, new_status: str, db: Session
) -> dict:
    req = db.scalars(
        select(ActionRequest).where(ActionRequest.id == request_id).with_for_update()
    ).first()
    if req is None:
        raise HTTPException(404, "Demande introuvable")
    if req.status != "pending":
        raise HTTPException(409, f"Demande déjà traitée ({req.status})")
    if approver == req.agent:
        raise HTTPException(403, "Le demandeur ne peut pas valider sa propre demande")
    req.status = new_status
    req.decided_by = approver
    req.decided_at = now()
    append_event(
        db,
        approver,
        f"action.{new_status}",
        {"request_id": req.id, "comment": comment},
    )
    db.commit()
    return action_to_dict(req)


@app.post("/actions/{request_id}/approve")
def approve(
    request_id: int,
    body: DecisionIn,
    approver: str = Depends(require_approver),
    db: Session = Depends(get_db),
):
    return decide(request_id, approver, body.comment, "approved", db)


@app.post("/actions/{request_id}/reject")
def reject(
    request_id: int,
    body: DecisionIn,
    approver: str = Depends(require_approver),
    db: Session = Depends(get_db),
):
    return decide(request_id, approver, body.comment, "rejected", db)


@app.post("/agent/run", status_code=201)
def agent_run(
    body: AgentIn,
    agent: str = Depends(require_agent),
    db: Session = Depends(get_db),
):
    # Le modèle externe ne reçoit que le texte masqué
    masked, mapping = mask(body.instruction)
    raw, cause = "", "proposition_mal_formee"
    try:
        proposal, mode, raw = propose(masked)
        candidate = ActionIn(
            action=proposal["action"],
            payload=unmask(proposal.get("payload", {}), mapping),
        )
    except Exception as exc:
        if isinstance(exc, AgentError):
            cause, raw = exc.kind, exc.raw
        append_event(
            db,
            agent,
            "agent.sortie_invalide",
            {"instruction": masked, "cause": cause, "sortie_brute": raw},
        )
        db.commit()
        raise HTTPException(502, "Sortie de l'agent invalide : aucune action transmise")
    append_event(
        db,
        agent,
        "agent.proposition",
        {
            "instruction": masked,
            "donnees_masquees": len(mapping),
            "mode": mode,
            "proposal": proposal,
        },
    )
    return submit_action(db, agent, candidate.action, candidate.payload)


@app.get("/events", dependencies=[Depends(current_user)])
def list_events(db: Session = Depends(get_db)):
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.id))
    return [event_to_dict(e) for e in events]


@app.get("/audit/verify", dependencies=[Depends(current_user)])
def verify(db: Session = Depends(get_db)):
    return verify_chain(db)

from audit import create_checkpoint


@app.post("/audit/checkpoint", status_code=201)
def checkpoint(
    approver: str = Depends(require_approver),
    db: Session = Depends(get_db),
):
    try:
        cp = create_checkpoint(db, approver)
    except ValueError:
        raise HTTPException(409, "Journal vide : rien à sceller")
    append_event(db, approver, "audit.scelle", {"last_id": cp["last_id"]})
    db.commit()
    return cp