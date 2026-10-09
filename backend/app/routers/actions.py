"""Persisted campus reports, emergency actions, audit history, and food information."""
import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.action_crypto import decrypt_private, encrypt_private
from app.audit import log_audit
from app.clock import get_now
from app.deps import get_current_user, get_db, require_roles
from app.models.actions import ReportHistory
from app.models.campus import Block, Floor, Room
from app.models.identity import User
from app.models.operations import MaintenanceTicket
from app.models.safety import EmergencyContact, EmergencyEvent, Incident
from app.models.workflow import Notification
from app.schemas.actions import (
    EmergencyContactCreate,
    EmergencyContactUpdate,
    EmergencyCreate,
    ReportCreate,
    ReportNote,
    ReportUpdate,
)

router = APIRouter()

REPORT_TABLES = {
    "MAINTENANCE": MaintenanceTicket,
    "GENERAL": MaintenanceTicket,
    "SAFETY": Incident,
    "EMERGENCY": EmergencyEvent,
}
STATUSES = {
    "MAINTENANCE": {"OPEN", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"},
    "GENERAL": {"OPEN", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"},
    "SAFETY": {"SUBMITTED", "UNDER_REVIEW", "ASSIGNED", "INVESTIGATION", "RESOLVED", "CLOSED", "REJECTED"},
    "EMERGENCY": {"OPEN", "ACKNOWLEDGED", "RESPONDING", "RESOLVED", "CANCELLED"},
}
MAINTENANCE_CATEGORIES = {
    "CLASSROOM", "ELECTRICAL", "PLUMBING", "FURNITURE", "PROJECTOR / SMART BOARD",
    "WI-FI / NETWORK", "CLEANING", "WASHROOM", "LABORATORY", "SECURITY",
    "PARKING", "WATER", "OTHER",
}
SAFETY_CATEGORIES = {
    "HARASSMENT", "BULLYING", "THREAT", "UNSAFE AREA", "SUSPICIOUS ACTIVITY",
    "VIOLENCE", "DISCRIMINATION", "OTHER SAFETY CONCERN",
}
EMERGENCY_CATEGORIES = {
    "MEDICAL EMERGENCY", "FIRE", "SECURITY EMERGENCY", "ACCIDENT",
    "THREAT / VIOLENCE", "OTHER",
}


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:14]}"


def _new_code(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _notify(db: Session, audience_id: str, kind: str, title: str, body: str, payload: dict[str, Any] | None = None) -> None:
    db.add(Notification(
        id=_id("notif"),
        audience_type="USER" if audience_id not in {"MANAGEMENT"} else "ROLE",
        audience_id=audience_id,
        type=kind,
        title=title,
        body=body,
        payload=payload,
        created_at=get_now(),
    ))


def _record_history(
    db: Session,
    report_type: str,
    report_id: str,
    event: str,
    user: User | None,
    old_value: str | None = None,
    new_value: str | None = None,
    note: str | None = None,
    internal: bool = False,
) -> None:
    db.add(ReportHistory(
        id=_id("rhist"),
        report_type=report_type,
        report_id=report_id,
        event=event,
        old_value=old_value,
        new_value=new_value,
        changed_by=user.id if user else None,
        changed_at=get_now(),
        note=note,
        internal=internal,
    ))


def _find_report(db: Session, key: str) -> tuple[str, Any] | None:
    for report_type, model in REPORT_TABLES.items():
        record = db.query(model).filter((model.id == key) | (model.code == key)).first()
        if record:
            if report_type == "MAINTENANCE" and record.report_type == "GENERAL":
                report_type = "GENERAL"
            return report_type, record
    return None


def _owner_id(report_type: str, record: Any) -> str | None:
    if report_type == "SAFETY":
        return record.reporter_user_id
    if report_type == "EMERGENCY":
        return record.user_id
    return record.reported_by


def _is_anonymous(report_type: str, record: Any) -> bool:
    return report_type == "SAFETY" and bool(record.anonymous)


def _report_values(report_type: str, record: Any) -> dict[str, Any]:
    if report_type in {"MAINTENANCE", "GENERAL"}:
        return {
            "id": record.id,
            "code": record.code,
            "category": record.category,
            "description": record.description,
            "room_id": record.room_id,
            "location_text": record.location_text,
            "status": record.status,
            "priority": record.priority or "MEDIUM",
            "severity": None,
            "assigned_to": record.assigned_to,
            "created_at": record.created_at,
            "updated_at": record.updated_at or record.created_at,
            "resolved_at": record.resolved_at,
            "resolution_note": record.resolution_note,
            "anonymous": False,
        }
    if report_type == "SAFETY":
        return {
            "id": record.id,
            "code": record.code,
            "category": record.category,
            "description": decrypt_private(record.description_enc),
            "room_id": record.location_room_id,
            "location_text": decrypt_private(record.location_enc),
            "status": str(record.status).upper(),
            "priority": record.priority or record.severity or "MEDIUM",
            "severity": record.severity or "MEDIUM",
            "assigned_to": record.assigned_to,
            "created_at": record.incident_dt,
            "updated_at": record.updated_at or record.incident_dt,
            "resolved_at": record.resolved_at,
            "resolution_note": decrypt_private(record.resolution_note),
            "anonymous": bool(record.anonymous),
        }
    return {
        "id": record.id,
        "code": record.code or _new_code("ER"),
        "category": record.category or "Emergency",
        "description": decrypt_private(record.description_enc) or "",
        "room_id": record.room_id,
        "location_text": decrypt_private(record.location_text),
        "status": str(record.status).upper(),
        "priority": "CRITICAL",
        "severity": record.severity or "CRITICAL",
        "assigned_to": record.assigned_to,
        "created_at": record.created_at,
        "updated_at": record.updated_at or record.created_at,
        "resolved_at": record.resolved_at,
        "resolution_note": decrypt_private(record.resolution_note),
        "anonymous": False,
    }


def _serialize_report(
    db: Session,
    report_type: str,
    record: Any,
    user: User,
    include_private: bool,
) -> dict[str, Any]:
    values = _report_values(report_type, record)
    room = db.query(Room).filter(Room.id == values["room_id"]).first() if values["room_id"] else None
    floor = db.query(Floor).filter(Floor.id == room.floor_id).first() if room else None
    block = db.query(Block).filter(Block.id == room.block_id).first() if room else None
    owner_id = _owner_id(report_type, record)
    owner = db.query(User).filter(User.id == owner_id).first() if owner_id else None

    if values["anonymous"]:
        reporter = "Anonymous Reporter"
    elif owner_id == user.id:
        reporter = "You"
    else:
        reporter = owner.display_name or owner.email if owner else "Campus user"

    result = {
        "id": values["id"],
        "code": values["code"],
        "report_type": report_type,
        "category": values["category"],
        "description": values["description"] if include_private else None,
        "room_id": room.id if room else None,
        "room_code": room.code if room else None,
        "location": " · ".join(
            part for part in (
                block.name if block else None,
                floor.name if floor else None,
                room.code if room else values["location_text"],
            ) if part
        ) or "Location not provided",
        "location_text": values["location_text"] if include_private and not room else None,
        "reporter": reporter,
        "priority": values["priority"],
        "severity": values["severity"],
        "status": values["status"],
        "assigned_to": values["assigned_to"],
        "created_at": values["created_at"],
        "updated_at": values["updated_at"],
        "resolved_at": values["resolved_at"],
        "resolution_note": values["resolution_note"] if include_private else None,
        "is_mine": owner_id == user.id,
        "anonymous": values["anonymous"],
    }
    if not include_private:
        result["assigned_to"] = None
    return result


def _create_report(db: Session, report_type: str, data: Any, user: User) -> dict[str, Any]:
    if data.room_id and not db.query(Room.id).filter(Room.id == data.room_id).first():
        raise HTTPException(status_code=422, detail="Select a valid campus room.")
    if report_type in {"MAINTENANCE", "SAFETY", "EMERGENCY"} and not data.room_id and not data.location_text:
        raise HTTPException(status_code=422, detail="Provide a campus room or a location description.")

    now = get_now()
    category = data.category.strip()
    report_id: str
    if report_type in {"MAINTENANCE", "GENERAL"}:
        prefix = "ISS"
        record = MaintenanceTicket(
            id=_id("ticket"),
            code=_new_code(prefix),
            room_id=data.room_id,
            location_text=data.location_text,
            category=category,
            description=data.description,
            report_type=report_type,
            priority="MEDIUM",
            status="OPEN",
            reported_by=user.id,
            created_at=now,
            updated_at=now,
        )
        db.add(record)
        report_id = record.id
    elif report_type == "SAFETY":
        record = Incident(
            id=_id("incident"),
            code=_new_code("SR"),
            reporter_user_id=user.id,
            category=category,
            description_enc=encrypt_private(data.description),
            location_enc=encrypt_private(data.location_text),
            location_room_id=data.room_id,
            incident_dt=now,
            status="SUBMITTED",
            anonymous=bool(data.anonymous),
            severity="MEDIUM",
            priority="MEDIUM",
            updated_at=now,
        )
        db.add(record)
        report_id = record.id
    else:
        record = EmergencyEvent(
            id=_id("emerg"),
            user_id=user.id,
            created_at=now,
            location_text=encrypt_private(data.location_text),
            location_shared=False,
            status="OPEN",
            code=_new_code("ER"),
            category=category,
            description_enc=encrypt_private(data.description),
            room_id=data.room_id,
            severity="CRITICAL",
            priority="CRITICAL",
            updated_at=now,
        )
        db.add(record)
        report_id = record.id

    _record_history(db, report_type, report_id, "CREATED", user, new_value="OPEN" if report_type != "SAFETY" else "SUBMITTED")
    public_code = record.code
    reporter_body = (
        f"Your safety report {public_code} has been received and is under review."
        if report_type == "SAFETY"
        else f"Your report {public_code} has been submitted."
        if report_type in {"MAINTENANCE", "GENERAL"}
        else f"Emergency {public_code} has been submitted to campus management. No external emergency service is contacted by this system."
    )
    _notify(db, user.id, "CAMPUS_REPORT", f"{public_code} submitted", reporter_body, {"report_code": public_code})
    management_title = (
        f"Critical emergency {public_code}"
        if report_type == "EMERGENCY"
        else f"New safety report {public_code}"
        if report_type == "SAFETY"
        else f"New campus report {public_code}"
    )
    _notify(db, "MANAGEMENT", "CAMPUS_REPORT", management_title, f"{category} · {report_type.lower()} report received.", {"report_code": public_code})
    log_audit(db, user.id, "CREATE_CAMPUS_REPORT", "CampusReport", report_id, {
        "report_code": public_code,
        "report_type": report_type,
        "category": category,
        "anonymous": bool(getattr(data, "anonymous", False)),
    }, role=user.role)
    db.commit()
    db.refresh(record)
    return _serialize_report(db, report_type, record, user, include_private=True)


def _can_view_safety(user: User) -> bool:
    return user.role == "MANAGEMENT" or (user.role == "SAFETY" and bool(user.can_view_incidents))


def _access_report(db: Session, key: str, user: User) -> tuple[str, Any, bool]:
    found = _find_report(db, key)
    if not found:
        raise HTTPException(status_code=404, detail="Report not found.")
    report_type, record = found
    is_owner = _owner_id(report_type, record) == user.id
    if report_type == "SAFETY" and not (is_owner or _can_view_safety(user)):
        raise HTTPException(status_code=404, detail="Report not found.")
    if report_type != "SAFETY" and not (is_owner or user.role == "MANAGEMENT"):
        if not (user.role == "MAINTENANCE" and record.assigned_to == user.display_name):
            raise HTTPException(status_code=404, detail="Report not found.")
    return report_type, record, is_owner


@router.post("/reports", status_code=status.HTTP_201_CREATED)
def create_report(
    body: ReportCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in {"STUDENT", "FACULTY"}:
        raise HTTPException(status_code=403, detail="Only students and faculty can submit campus reports.")
    report_type = body.report_type
    category_key = body.category.strip().upper()
    if report_type == "MAINTENANCE" and category_key not in MAINTENANCE_CATEGORIES:
        raise HTTPException(status_code=422, detail="Choose a supported campus issue category.")
    if report_type == "SAFETY" and category_key not in SAFETY_CATEGORIES:
        raise HTTPException(status_code=422, detail="Choose a supported safety category.")
    if body.anonymous and report_type != "SAFETY":
        raise HTTPException(status_code=422, detail="Anonymous submission is available only for safety reports.")
    return _create_report(db, report_type, body, user)


@router.post("/emergency", status_code=status.HTTP_201_CREATED)
def create_emergency(
    body: EmergencyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in {"STUDENT", "FACULTY"}:
        raise HTTPException(status_code=403, detail="Emergency reports are available to students and faculty.")
    if body.category.strip().upper() not in EMERGENCY_CATEGORIES:
        raise HTTPException(status_code=422, detail="Choose a supported emergency category.")
    return _create_report(db, "EMERGENCY", body, user)


@router.get("/emergency-contacts")
def list_emergency_contacts(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["STUDENT"])),
):
    contacts = db.query(EmergencyContact).filter(
        EmergencyContact.user_id == user.id
    ).order_by(EmergencyContact.name).all()
    return [_emergency_contact_values(contact) for contact in contacts]


@router.post("/emergency-contacts", status_code=status.HTTP_201_CREATED)
def create_emergency_contact(
    body: EmergencyContactCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["STUDENT"])),
):
    contact = EmergencyContact(
        id=_id("contact"),
        user_id=user.id,
        name=body.name,
        relationship=body.relationship,
        phone_number=body.phone_number,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return _emergency_contact_values(contact)


@router.patch("/emergency-contacts/{contact_id}")
def update_emergency_contact(
    contact_id: str,
    body: EmergencyContactUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["STUDENT"])),
):
    contact = db.query(EmergencyContact).filter(
        EmergencyContact.id == contact_id,
        EmergencyContact.user_id == user.id,
    ).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="Emergency contact not found.")
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Provide at least one contact field to update.")
    for key, value in updates.items():
        setattr(contact, key, value)
    db.commit()
    db.refresh(contact)
    return _emergency_contact_values(contact)


@router.delete("/emergency-contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_emergency_contact(
    contact_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["STUDENT"])),
):
    contact = db.query(EmergencyContact).filter(
        EmergencyContact.id == contact_id,
        EmergencyContact.user_id == user.id,
    ).first()
    if contact is None:
        raise HTTPException(status_code=404, detail="Emergency contact not found.")
    db.delete(contact)
    db.commit()


def _emergency_contact_values(contact: EmergencyContact) -> dict[str, str]:
    return {
        "id": contact.id,
        "name": contact.name,
        "relationship": contact.relationship,
        "phone_number": contact.phone_number,
    }


@router.get("/reports")
def list_reports(
    report_type: str | None = Query(default=None),
    report_status: str | None = Query(default=None, alias="status"),
    category: str | None = None,
    priority: str | None = None,
    location: str | None = None,
    mine: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    records: list[tuple[str, Any]] = []
    if report_type is None or report_type in {"MAINTENANCE", "GENERAL"}:
        query = db.query(MaintenanceTicket)
        if user.role != "MANAGEMENT" or mine:
            query = query.filter(MaintenanceTicket.reported_by == user.id)
        records.extend(
            (record.report_type or "MAINTENANCE", record)
            for record in query.order_by(MaintenanceTicket.created_at.desc()).limit(300).all()
        )
    if report_type is None or report_type == "SAFETY":
        if not mine and user.role in {"MANAGEMENT", "SAFETY"} and (user.role == "MANAGEMENT" or _can_view_safety(user)):
            safety_query = db.query(Incident)
        else:
            safety_query = db.query(Incident).filter(Incident.reporter_user_id == user.id)
        records.extend(("SAFETY", record) for record in safety_query.order_by(Incident.incident_dt.desc()).limit(300).all())
    if report_type is None or report_type == "EMERGENCY":
        emergency_query = db.query(EmergencyEvent)
        if user.role != "MANAGEMENT" or mine:
            emergency_query = emergency_query.filter(EmergencyEvent.user_id == user.id)
        records.extend(("EMERGENCY", record) for record in emergency_query.order_by(EmergencyEvent.created_at.desc()).limit(300).all())

    if report_type and report_type not in REPORT_TABLES:
        raise HTTPException(status_code=422, detail="Unsupported report type.")
    result = []
    for kind, record in records:
        values = _report_values(kind, record)
        if report_type and kind != report_type:
            continue
        if report_status and values["status"] != report_status.upper():
            continue
        if category and category.casefold() not in values["category"].casefold():
            continue
        if priority and values["priority"] != priority.upper() and values["severity"] != priority.upper():
            continue
        serialized = _serialize_report(db, kind, record, user, include_private=True)
        if location and location.casefold() not in serialized["location"].casefold():
            continue
        result.append(serialized)
    return sorted(result, key=lambda item: item["created_at"], reverse=True)


@router.get("/reports/summary")
def report_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    reports = []
    for model, kind in (
        (MaintenanceTicket, "MAINTENANCE"),
        (Incident, "SAFETY"),
        (EmergencyEvent, "EMERGENCY"),
    ):
        records = db.query(model).all()
        for record in records:
            actual_kind = record.report_type if model is MaintenanceTicket and record.report_type == "GENERAL" else kind
            report = _report_values(actual_kind, record)
            report["report_type"] = actual_kind
            reports.append(report)
    today = get_now().date()
    return {
        "total": len(reports),
        "open": sum(report["status"] in {"OPEN", "SUBMITTED", "UNDER_REVIEW", "ACKNOWLEDGED"} for report in reports),
        "critical": sum(report["priority"] == "CRITICAL" or report["severity"] == "CRITICAL" for report in reports),
        "high": sum(report["priority"] == "HIGH" or report["severity"] == "HIGH" for report in reports),
        "in_progress": sum(report["status"] in {"IN_PROGRESS", "INVESTIGATION", "RESPONDING"} for report in reports),
        "resolved_today": sum(report["resolved_at"] is not None and report["resolved_at"].date() == today for report in reports),
        "by_type": {kind: sum(report["report_type"] == kind for report in reports) for kind in REPORT_TABLES},
        "historical_data_available": bool(reports),
    }


@router.get("/reports/{report_key}")
def get_report(
    report_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    report_type, record, is_owner = _access_report(db, report_key, user)
    return _serialize_report(db, report_type, record, user, include_private=is_owner or user.role == "MANAGEMENT" or _can_view_safety(user))


@router.patch("/reports/{report_key}")
def update_report(
    report_key: str,
    body: ReportUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    report_type, record, _ = _access_report(db, report_key, user)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Provide at least one report field to update.")
    if updates.get("status") is not None:
        new_status = updates["status"].strip().upper()
        if new_status not in STATUSES[report_type]:
            raise HTTPException(status_code=422, detail=f"Invalid status for {report_type.lower()} report.")
        old_status = _report_values(report_type, record)["status"]
        if new_status != old_status:
            record.status = new_status
            _record_history(db, report_type, record.id, "STATUS_CHANGED", user, old_status, new_status)
            if new_status == "RESOLVED":
                record.resolved_at = get_now()
                if updates.get("resolution_note"):
                    record.resolution_note = encrypt_private(updates["resolution_note"]) if report_type in {"SAFETY", "EMERGENCY"} else updates["resolution_note"]
            elif new_status not in {"CLOSED", "CANCELLED", "REJECTED"}:
                record.resolved_at = None
            owner_id = _owner_id(report_type, record)
            if owner_id:
                code = _report_values(report_type, record)["code"]
                _notify(db, owner_id, "CAMPUS_REPORT_STATUS", f"{code} status updated", f"Your report {code} is now {new_status.replace('_', ' ').title()}.", {"report_code": code, "status": new_status})
    if updates.get("priority") is not None or updates.get("severity") is not None:
        column_name = "severity" if report_type in {"SAFETY", "EMERGENCY"} else "priority"
        new_value = updates.get(column_name) or updates.get("priority") or updates.get("severity")
        old_value = getattr(record, column_name, None)
        if old_value != new_value:
            setattr(record, column_name, new_value)
            if report_type == "SAFETY":
                record.priority = new_value
            _record_history(db, report_type, record.id, "PRIORITY_CHANGED", user, old_value, new_value)
    if "assigned_to" in updates:
        old_assignment = getattr(record, "assigned_to", None)
        new_assignment = updates["assigned_to"]
        if old_assignment != new_assignment:
            record.assigned_to = new_assignment
            _record_history(db, report_type, record.id, "ASSIGNED", user, old_assignment, new_assignment)
            owner_id = _owner_id(report_type, record)
            if owner_id:
                code = _report_values(report_type, record)["code"]
                _notify(db, owner_id, "CAMPUS_REPORT_ASSIGNED", f"{code} assigned", f"Your report {code} has been assigned to {new_assignment or 'the campus team'}.", {"report_code": code})
    if updates.get("resolution_note") and not updates.get("status"):
        record.resolution_note = encrypt_private(updates["resolution_note"]) if report_type in {"SAFETY", "EMERGENCY"} else updates["resolution_note"]
        _record_history(db, report_type, record.id, "RESOLUTION_NOTE_ADDED", user, note="Resolution details updated.", internal=True)

    record.updated_at = get_now()
    code = _report_values(report_type, record)["code"]
    log_audit(db, user.id, "UPDATE_CAMPUS_REPORT", "CampusReport", record.id, {"report_code": code, "fields": sorted(updates)}, role=user.role)
    db.commit()
    db.refresh(record)
    return _serialize_report(db, report_type, record, user, include_private=True)


@router.post("/reports/{report_key}/notes", status_code=status.HTTP_201_CREATED)
def add_report_note(
    report_key: str,
    body: ReportNote,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    report_type, record, _ = _access_report(db, report_key, user)
    _record_history(db, report_type, record.id, "NOTE_ADDED", user, note=body.note, internal=True)
    record.updated_at = get_now()
    log_audit(db, user.id, "ADD_CAMPUS_REPORT_NOTE", "CampusReport", record.id, {"report_code": _report_values(report_type, record)["code"]}, role=user.role)
    db.commit()
    return {"ok": True}


@router.get("/reports/{report_key}/history")
def get_report_history(
    report_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    report_type, record, is_owner = _access_report(db, report_key, user)
    can_see_internal = user.role == "MANAGEMENT" or _can_view_safety(user)
    query = db.query(ReportHistory).filter(
        ReportHistory.report_type == report_type,
        ReportHistory.report_id == record.id,
    )
    if not can_see_internal:
        query = query.filter(ReportHistory.internal.is_(False))
    history = query.order_by(ReportHistory.changed_at.asc()).all()
    result = []
    for item in history:
        actor = db.query(User).filter(User.id == item.changed_by).first() if item.changed_by else None
        result.append({
            "event": item.event,
            "old_value": item.old_value,
            "new_value": item.new_value,
            "changed_at": item.changed_at,
            "changed_by": actor.display_name if can_see_internal and actor else "Campus team",
            "note": item.note if can_see_internal or not item.internal else None,
        })
    return result
