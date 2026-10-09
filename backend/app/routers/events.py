"""Audience-scoped event proposals, management decisions, and publication."""
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.clock import get_now
from app.deps import get_current_user, get_db, require_roles
from app.models.academic import Faculty
from app.models.identity import User
from app.models.operations import Event
from app.models.workflow import Notification
from app.schemas.events import (
    CampusEventResponse,
    EventDecision,
    EventProposalCreate,
    EventRejection,
)

router = APIRouter()
AUDIENCE_ROLES = {
    "STUDENTS": ["STUDENT"],
    "FACULTY": ["FACULTY"],
    "STUDENTS_AND_FACULTY": ["STUDENT", "FACULTY"],
}


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)
    return value


def _audience_roles(audience: object) -> set[str]:
    if audience is None:
        return {"STUDENT", "FACULTY"}
    if isinstance(audience, str):
        values = [audience]
    elif isinstance(audience, list):
        values = audience
    elif isinstance(audience, dict):
        if audience.get("all") is True:
            return {"STUDENT", "FACULTY"}
        values = audience.get("roles", [])
        if not isinstance(values, list):
            return set()
    else:
        return set()

    roles: set[str] = set()
    for value in values:
        role = str(value).strip().upper()
        if role in {"ALL", "STUDENTS_AND_FACULTY"}:
            roles.update({"STUDENT", "FACULTY"})
        elif role in {"STUDENT", "STUDENTS"}:
            roles.add("STUDENT")
        elif role in {"FACULTY", "TEACHERS"}:
            roles.add("FACULTY")
    return roles


def _audience_label(audience: object) -> str:
    roles = _audience_roles(audience)
    if roles == {"STUDENT", "FACULTY"}:
        return "UNSPECIFIED"
    if roles == {"STUDENT"}:
        return "STUDENTS"
    if roles == {"FACULTY"}:
        return "FACULTY"
    return "STUDENTS_AND_FACULTY"


def _event_response(
    db: Session,
    event: Event,
    *,
    management: bool = False,
    owner: bool = False,
) -> CampusEventResponse:
    creator = db.query(User).filter(User.id == event.created_by).first() if event.created_by else None
    return CampusEventResponse(
        id=event.id,
        title=event.title,
        category=event.category,
        description=event.description,
        start_dt=event.start_dt,
        end_dt=event.end_dt,
        location=event.location,
        organizer=event.organizer,
        audience=_audience_label(event.audience),
        status=event.status,
        created_at=event.created_at,
        updated_at=event.updated_at,
        created_by=event.created_by if management else None,
        created_by_name=(creator.display_name or creator.email) if management and creator else None,
        decision_reason=event.decision_reason if management or owner else None,
        notes=event.notes if management or owner else None,
        decided_by=event.decided_by if management else None,
        decided_at=event.decided_at if management else None,
    )


def _notify(
    db: Session,
    audience_type: str,
    audience_id: str,
    title: str,
    body: str,
    event_id: str,
) -> None:
    db.add(Notification(
        id=f"notif_{uuid.uuid4().hex[:14]}",
        audience_type=audience_type,
        audience_id=audience_id,
        type="EVENT",
        title=title,
        body=body,
        payload={"event_id": event_id},
        created_at=get_now(),
    ))


def _notify_owner(db: Session, event: Event, message: str) -> None:
    if event.created_by:
        _notify(
            db,
            "USER",
            event.created_by,
            f"Event proposal: {event.title}",
            message,
            event.id,
        )


def _get_event(db: Session, event_id: str) -> Event:
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found.")
    return event


def _require_owner_or_management(event: Event, user: User) -> bool:
    owner = user.role == "FACULTY" and event.created_by == user.id
    if not owner and user.role != "MANAGEMENT":
        raise HTTPException(status_code=404, detail="Event not found.")
    return owner


@router.get("/events", response_model=list[CampusEventResponse])
@router.get("/faculty/events", response_model=list[CampusEventResponse])
def list_published_events(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["STUDENT", "FACULTY", "MANAGEMENT"])),
):
    now = get_now()
    events = db.query(Event).filter(
        Event.status == "PUBLISHED",
        Event.start_dt >= now,
    ).order_by(Event.start_dt.asc()).all()
    if user.role == "MANAGEMENT":
        return [_event_response(db, event, management=True) for event in events]
    return [
        _event_response(db, event)
        for event in events
        if user.role in _audience_roles(event.audience)
    ]


@router.get("/events/{event_id}", response_model=CampusEventResponse)
def get_event(
    event_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["STUDENT", "FACULTY", "MANAGEMENT"])),
):
    event = _get_event(db, event_id)
    if user.role == "MANAGEMENT":
        return _event_response(db, event, management=True)
    owner = user.role == "FACULTY" and event.created_by == user.id
    if event.status == "PUBLISHED":
        if user.role not in _audience_roles(event.audience):
            raise HTTPException(status_code=404, detail="Event not found.")
    elif not owner:
        raise HTTPException(status_code=404, detail="Event not found.")
    return _event_response(db, event, owner=owner)


@router.post("/faculty/events", response_model=CampusEventResponse, status_code=201)
def propose_event(
    body: EventProposalCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    faculty = db.query(Faculty).filter(Faculty.user_id == user.id).first()
    if faculty is None:
        raise HTTPException(status_code=404, detail="Faculty profile is not provisioned.")
    start_dt = _normalize_datetime(body.start_dt)
    end_dt = _normalize_datetime(body.end_dt)
    if end_dt <= start_dt:
        raise HTTPException(status_code=422, detail="Event end time must be later than its start time.")
    if start_dt < get_now():
        raise HTTPException(status_code=422, detail="Event proposals must be for a future date and time.")

    normalized_title = body.title.casefold()
    duplicate = db.query(Event).filter(
        Event.created_by == user.id,
        Event.start_dt == start_dt,
        Event.status.in_(["PENDING_APPROVAL", "APPROVED", "PUBLISHED"]),
    ).all()
    if any(item.title.casefold() == normalized_title for item in duplicate):
        raise HTTPException(status_code=409, detail="You already have an active proposal for this event time.")

    event = Event(
        id=f"event_{uuid.uuid4().hex[:14]}",
        title=body.title,
        category=body.category,
        description=body.description,
        start_dt=start_dt,
        end_dt=end_dt,
        audience=AUDIENCE_ROLES[body.audience],
        status="PENDING_APPROVAL",
        location=body.location,
        organizer=body.organizer,
        created_by=user.id,
        created_at=get_now(),
        updated_at=get_now(),
        notes=body.notes,
    )
    db.add(event)
    log_audit(
        db, user.id, "PROPOSE_EVENT", "Event", event.id,
        {"title": event.title, "audience": body.audience},
        role=user.role,
    )
    db.commit()
    db.refresh(event)
    return _event_response(db, event, owner=True)


@router.get("/faculty/events/proposals", response_model=list[CampusEventResponse])
def list_faculty_event_proposals(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["FACULTY"])),
):
    events = db.query(Event).filter(
        Event.created_by == user.id,
    ).order_by(Event.created_at.desc(), Event.start_dt.asc()).all()
    return [_event_response(db, event, owner=True) for event in events]


@router.get("/management/events", response_model=list[CampusEventResponse])
def list_management_events(
    status_filter: str | None = Query(default=None, alias="status"),
    category: str | None = None,
    audience: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    query = db.query(Event)
    if status_filter:
        query = query.filter(Event.status == status_filter.upper())
    if category:
        query = query.filter(Event.category == category.upper())
    if date_from:
        query = query.filter(Event.start_dt >= _normalize_datetime(date_from))
    if date_to:
        query = query.filter(Event.start_dt <= _normalize_datetime(date_to))
    events = query.order_by(Event.created_at.desc(), Event.start_dt.asc()).all()
    if audience:
        desired_roles = set(AUDIENCE_ROLES.get(audience.upper(), []))
        events = [
            event for event in events
            if _audience_roles(event.audience) == desired_roles
        ]
    return [_event_response(db, event, management=True) for event in events]


@router.post("/management/events/{event_id}/approve", response_model=CampusEventResponse)
def approve_event(
    event_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    event = _get_event(db, event_id)
    if event.status != "PENDING_APPROVAL":
        raise HTTPException(status_code=409, detail="Only pending proposals can be approved.")
    event.status = "APPROVED"
    event.updated_at = get_now()
    event.decided_by = user.id
    event.decided_at = get_now()
    event.decision_reason = None
    _notify_owner(db, event, f"Your event proposal '{event.title}' was approved.")
    log_audit(db, user.id, "APPROVE_EVENT", "Event", event.id, {}, role=user.role)
    db.commit()
    db.refresh(event)
    return _event_response(db, event, management=True)


@router.post("/management/events/{event_id}/reject", response_model=CampusEventResponse)
def reject_event(
    event_id: str,
    body: EventRejection,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    event = _get_event(db, event_id)
    if event.status != "PENDING_APPROVAL":
        raise HTTPException(status_code=409, detail="Only pending proposals can be rejected.")
    event.status = "REJECTED"
    event.updated_at = get_now()
    event.decided_by = user.id
    event.decided_at = get_now()
    event.decision_reason = body.reason
    _notify_owner(db, event, f"Your event proposal '{event.title}' was rejected: {body.reason}")
    log_audit(db, user.id, "REJECT_EVENT", "Event", event.id, {"reason": body.reason}, role=user.role)
    db.commit()
    db.refresh(event)
    return _event_response(db, event, management=True)


@router.post("/management/events/{event_id}/publish", response_model=CampusEventResponse)
def publish_event(
    event_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    event = _get_event(db, event_id)
    if event.status != "APPROVED":
        raise HTTPException(status_code=409, detail="Only approved events can be published.")
    if event.start_dt < get_now():
        raise HTTPException(status_code=422, detail="Past events cannot be published.")
    roles = _audience_roles(event.audience)
    if not roles:
        raise HTTPException(status_code=422, detail="Select a valid event audience before publishing.")
    event.status = "PUBLISHED"
    event.updated_at = get_now()
    _notify_owner(db, event, f"Your event '{event.title}' has been published.")
    role_names = "students and faculty" if len(roles) == 2 else (
        "students" if "STUDENT" in roles else "faculty"
    )
    for role in sorted(roles):
        _notify(
            db,
            "ROLE",
            role,
            f"New event: {event.title}",
            f"'{event.title}' has been published for {role_names}.",
            event.id,
        )
    log_audit(
        db, user.id, "PUBLISH_EVENT", "Event", event.id,
        {"audience": sorted(roles)},
        role=user.role,
    )
    db.commit()
    db.refresh(event)
    return _event_response(db, event, management=True)


@router.post("/management/events/{event_id}/cancel", response_model=CampusEventResponse)
def cancel_event(
    event_id: str,
    body: EventDecision,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    event = _get_event(db, event_id)
    if event.status not in {"PENDING_APPROVAL", "APPROVED", "PUBLISHED"}:
        raise HTTPException(status_code=409, detail="This event cannot be cancelled in its current status.")
    was_published = event.status == "PUBLISHED"
    event.status = "CANCELLED"
    event.updated_at = get_now()
    event.decided_by = user.id
    event.decided_at = get_now()
    event.decision_reason = body.reason
    _notify_owner(db, event, f"Your event '{event.title}' was cancelled.")
    if was_published:
        for role in sorted(_audience_roles(event.audience)):
            _notify(
                db,
                "ROLE",
                role,
                f"Event cancelled: {event.title}",
                body.reason or f"'{event.title}' has been cancelled.",
                event.id,
            )
    log_audit(
        db, user.id, "CANCEL_EVENT", "Event", event.id,
        {"reason": body.reason},
        role=user.role,
    )
    db.commit()
    db.refresh(event)
    return _event_response(db, event, management=True)
