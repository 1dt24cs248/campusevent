"""Scenario simulation, approval, and publish router (M3 + M4)."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List

from app.deps import get_db, get_current_user, require_roles
from app.models.identity import User
from app.models.academic import Faculty, Section, Subject
from app.models.campus import Room
from app.models.scenario import (
    Scenario, ScenarioChange, OptimizationRun, Approval, PublishedVersion,
)
from app.models.schedule import SessionOverride, TimetableEntry
from app.models.workflow import Notification
from app.audit import log_audit
from app.clock import get_now
from app.engine.slots import PERIOD_SLOTS, SLOTS, SLOT_INDEX, WEEKDAYS
from app.schemas.scenario import (
    ScenarioCreate, ScenarioResponse, SimulationRequest, SimulationResponse,
    SolverResultResponse, ApprovalRequest, PublishResponse, VersionResponse,
    NotificationResponse,
)

router = APIRouter()

# ------------- Scenario CRUD --------------------------------------------------

@router.post("/scenarios", response_model=ScenarioResponse)
def create_scenario(
    body: ScenarioCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    """Create a new What-If scenario."""
    # Capture current published version as base_version_id
    current_version = db.query(PublishedVersion).order_by(
        PublishedVersion.version_no.desc()
    ).first()
    base_version_id = current_version.id if current_version else None

    scenario = Scenario(
        id=f"scen_{uuid.uuid4().hex[:10]}",
        name=body.name,
        category=body.category,
        status="DRAFT",
        created_by=user.id,
        objective_preset=body.objective_preset,
        base_version_id=base_version_id,
        created_at=get_now(),
    )
    db.add(scenario)
    db.flush()

    for ch in body.changes:
        db.add(ScenarioChange(
            id=f"sch_{uuid.uuid4().hex[:10]}",
            scenario_id=scenario.id,
            type=ch.type,
            payload=ch.payload,
        ))

    log_audit(db, user.id, "CREATE_SCENARIO", "Scenario", scenario.id,
              {"name": body.name, "changes": len(body.changes), "base_version_id": base_version_id}, role=user.role)
    db.commit()
    return _scenario_response(scenario, db)


@router.get("/scenarios", response_model=List[ScenarioResponse])
def list_scenarios(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    """List all scenarios (Management only)."""
    scenarios = db.query(Scenario).order_by(Scenario.created_at.desc()).all()
    return [_scenario_response(s, db) for s in scenarios]


@router.get("/scenarios/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(
    scenario_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    """Get scenario details (Management only)."""
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(404, "Scenario not found")
    return _scenario_response(scenario, db)


@router.delete("/scenarios/{scenario_id}")
def delete_scenario(
    scenario_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    """Delete a draft scenario."""
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(404, "Scenario not found")
    if scenario.status not in ("DRAFT", "SIMULATED"):
        raise HTTPException(400, "Cannot delete scenario in this status")
    db.query(ScenarioChange).filter(ScenarioChange.scenario_id == scenario_id).delete()
    db.query(OptimizationRun).filter(OptimizationRun.scenario_id == scenario_id).delete()
    db.delete(scenario)
    db.commit()
    return {"ok": True}


# ------------- Simulation (M3) ------------------------------------------------

@router.post("/scenarios/{scenario_id}/simulate", response_model=SimulationResponse)
def simulate_scenario(
    scenario_id: str,
    body: SimulationRequest = SimulationRequest(),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    """Run CP-SAT simulation for a scenario."""
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(404, "Scenario not found")

    changes_db = db.query(ScenarioChange).filter(
        ScenarioChange.scenario_id == scenario_id
    ).all()
    changes = [{"type": c.type, "payload": c.payload} for c in changes_db]

    if not changes:
        raise HTTPException(400, "Scenario has no changes defined")

    # Run simulation
    from app.engine.state import run_scenario_simulation
    scenario_state, results = run_scenario_simulation(
        db, changes,
        strategies=body.strategies,
        time_limit_sec=body.time_limit_sec or 8,
    )

    # Store optimization runs
    db.query(OptimizationRun).filter(
        OptimizationRun.scenario_id == scenario_id
    ).delete()

    run_objs = []
    for r in results:
        result_rows = _build_result_rows(db, r.assignments, r.unresolved, r.explanations)
        unresolved_ids = {
            item.get("entry_id") for item in r.unresolved if item.get("entry_id")
        }
        r.metrics.update({
            "affected_classes": r.metrics.get("total_entries", len(r.assignments) + len(unresolved_ids)),
            "reassigned_classes": sum(1 for row in result_rows if row["status"] == "REASSIGNED"),
            "unchanged_classes": sum(1 for row in result_rows if row["status"] == "UNCHANGED"),
            "unresolved_classes": len(unresolved_ids),
        })
        run = OptimizationRun(
            id=f"run_{uuid.uuid4().hex[:10]}",
            scenario_id=scenario_id,
            option_label=r.option_label,
            strategy=r.strategy,
            status=r.status,
            metrics=r.metrics,
            assignments=r.assignments,
            unresolved=r.unresolved,
            explanations=r.explanations,
            recovery=r.recovery,
            solve_ms=r.solve_ms,
            created_at=get_now(),
        )
        db.add(run)
        run_objs.append(run)

    scenario.status = "SIMULATED"
    log_audit(db, user.id, "SIMULATE_SCENARIO", "Scenario", scenario_id,
              {"affected": len(scenario_state.affected_entry_ids), "options": len(results)},
              role=user.role)
    db.commit()

    return SimulationResponse(
        scenario_id=scenario_id,
        affected_count=len(scenario_state.affected_entry_ids),
        change_descriptions=scenario_state.change_descriptions,
        options=[SolverResultResponse(
            run_id=run_objs[i].id,
            status=r.status,
            option_label=r.option_label,
            strategy=r.strategy,
            assignments=r.assignments,
            unresolved=r.unresolved,
            metrics=r.metrics,
            explanations=r.explanations,
            result_rows=result_rows,
            recovery=r.recovery,
            solve_ms=r.solve_ms,
        ) for i, r in enumerate(results)],
    )


@router.get("/scenarios/{scenario_id}/result", response_model=SimulationResponse)
def get_scenario_result(
    scenario_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    """Get stored simulation results (Management only)."""
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(404, "Scenario not found")

    runs = db.query(OptimizationRun).filter(
        OptimizationRun.scenario_id == scenario_id
    ).all()

    changes_db = db.query(ScenarioChange).filter(
        ScenarioChange.scenario_id == scenario_id
    ).all()

    return SimulationResponse(
        scenario_id=scenario_id,
        affected_count=sum(r.metrics.get("total_entries", 0) for r in runs[:1]),
        change_descriptions=[f"{c.type}: {c.payload}" for c in changes_db],
        options=[SolverResultResponse(
            run_id=r.id,
            status=r.status,
            option_label=r.option_label or "",
            strategy=r.strategy or "",
            assignments=r.assignments or {},
            unresolved=r.unresolved or [],
            metrics=r.metrics or {},
            explanations=r.explanations or {},
            result_rows=_build_result_rows(db, r.assignments or {}, r.unresolved or [], r.explanations or {}),
            recovery=r.recovery or [],
            solve_ms=r.solve_ms or 0,
        ) for r in runs],
    )


def _build_result_rows(
    db: Session,
    assignments: dict,
    unresolved: List[dict],
    explanations: dict,
) -> List[dict]:
    """Join optimizer output to the current timetable and campus records."""
    unresolved_by_id = {
        item.get("entry_id"): item
        for item in unresolved
        if item.get("entry_id")
    }
    entry_ids = set(assignments) | set(unresolved_by_id)
    entries = db.query(TimetableEntry).filter(TimetableEntry.id.in_(entry_ids)).all() if entry_ids else []
    sections = {item.id: item for item in db.query(Section).all()}
    subjects = {item.id: item for item in db.query(Subject).all()}
    faculty = {item.id: item for item in db.query(Faculty).all()}
    room_ids = {
        room_id
        for entry in entries
        for room_id in (entry.base_room_id, assignments.get(entry.id))
        if room_id
    }
    rooms = {item.id: item for item in db.query(Room).filter(Room.id.in_(room_ids)).all()} if room_ids else {}
    rows = []
    for entry in entries:
        section = sections.get(entry.section_id)
        subject = subjects.get(entry.subject_id)
        instructor = faculty.get(entry.faculty_id)
        original_room = rooms.get(entry.base_room_id)
        assigned_room_id = assignments.get(entry.id)
        assigned_room = rooms.get(assigned_room_id)
        unresolved_item = unresolved_by_id.get(entry.id)

        if unresolved_item:
            status_value = "UNRESOLVED"
            reason = unresolved_item.get("reason") or (
                "No feasible room satisfies the capacity, facility, availability, and time constraints."
            )
        elif assigned_room_id and assigned_room_id == entry.base_room_id:
            status_value = "UNCHANGED"
            reason = explanations.get(entry.id) or "The optimizer retained the original room assignment."
        else:
            status_value = "REASSIGNED"
            reason = explanations.get(entry.id) or "The optimizer selected a feasible alternative room."

        slot_index = SLOT_INDEX.get(entry.start_slot)
        start_time = end_time = None
        if slot_index is not None and entry.start_slot in SLOTS:
            start_time = SLOTS[entry.start_slot][0].strftime("%H:%M")
            end_index = slot_index + max(entry.duration_slots, 1) - 1
            if end_index < len(PERIOD_SLOTS):
                end_slot = PERIOD_SLOTS[end_index]
                end_time = SLOTS[end_slot][1].strftime("%H:%M")

        rows.append({
            "timetable_entry_id": entry.id,
            "subject_code": subject.code if subject else None,
            "subject_name": subject.name if subject else None,
            "section_code": section.code if section else None,
            "section_name": section.name if section else None,
            "academic_year": section.year if section else None,
            "faculty_id": entry.faculty_id,
            "faculty_name": instructor.name if instructor else None,
            "weekday": entry.weekday,
            "day": WEEKDAYS.get(entry.weekday),
            "start_time": start_time,
            "end_time": end_time,
            "original_room_id": entry.base_room_id,
            "original_room_name": original_room.display_name if original_room else None,
            "original_room_code": original_room.code if original_room else None,
            "assigned_room_id": assigned_room_id,
            "assigned_room_name": assigned_room.display_name if assigned_room else None,
            "assigned_room_code": assigned_room.code if assigned_room else None,
            "class_strength": section.strength if section else None,
            "room_capacity": assigned_room.capacity if assigned_room else None,
            "required_facilities": entry.required_facilities or [],
            "status": status_value,
            "reason": reason,
        })
    return rows


# ------------- Scenario Presets ------------------------------------------------

SCENARIO_PRESETS = {
    "hero_event": {
        "name": "College Event - Floor 1 Rooms Reserved",
        "category": "RESERVE_ROOMS",
        "changes": [{
            "type": "ROOM_UNAVAILABLE",
            "payload": {
                "room_ids": ["room_A101", "room_A102", "room_A103", "room_A104"],
                "time_from": "10:25",
                "time_to": "11:20",
                "reason_type": "EVENT",
                "label": "College Cultural Event"
            }
        }]
    },
    "floor1_closure": {
        "name": "Complete Floor 1 Closure",
        "category": "FLOOR_UNAVAILABLE",
        "changes": [{
            "type": "ROOM_UNAVAILABLE",
            "payload": {
                "room_ids": ["room_A101", "room_A102", "room_A103", "room_A104",
                             "room_A105", "room_A106", "room_A107", "room_A108",
                             "room_cse_lab_1", "room_cse_lab_2", "room_A1_SPARE"],
                "time_from": "09:30",
                "time_to": "17:00",
                "reason_type": "CLOSURE",
                "label": "Floor 1 maintenance closure"
            }
        }]
    },
    "strength_increase": {
        "name": "Section 3CSE-A Strength 63 -> 75",
        "category": "CHANGE_STRENGTH",
        "changes": [{
            "type": "CHANGE_STRENGTH",
            "payload": {
                "section_id": "sec_3cse_a",
                "new_strength": 75
            }
        }]
    },
    "stress_test_5": {
        "name": "Stress Test: 5 Busiest Rooms Closed",
        "category": "STRESS_TEST",
        "changes": [{
            "type": "STRESS_TEST",
            "payload": {"k": 5}
        }]
    },
}


@router.post("/scenarios/presets/{key}", response_model=ScenarioResponse)
def create_from_preset(
    key: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    """Create scenario from a predefined preset."""
    preset = SCENARIO_PRESETS.get(key)
    if not preset:
        raise HTTPException(404, f"Preset '{key}' not found. Available: {list(SCENARIO_PRESETS.keys())}")

    scenario = Scenario(
        id=f"scen_{uuid.uuid4().hex[:10]}",
        name=preset["name"],
        category=preset.get("category"),
        status="DRAFT",
        created_by=user.id,
        created_at=get_now(),
    )
    db.add(scenario)
    db.flush()

    for ch in preset["changes"]:
        db.add(ScenarioChange(
            id=f"sch_{uuid.uuid4().hex[:10]}",
            scenario_id=scenario.id,
            type=ch["type"],
            payload=ch["payload"],
        ))

    db.commit()
    return _scenario_response(scenario, db)


# ------------- Review / Approve / Publish (M4) ----------------------------------

@router.post("/scenarios/{scenario_id}/review")
def review_scenario(
    scenario_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    """Move scenario to REVIEWED status."""
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(404, "Scenario not found")
    if scenario.status != "SIMULATED":
        raise HTTPException(400, f"Cannot review scenario in status: {scenario.status}")
    scenario.status = "REVIEWED"
    log_audit(db, user.id, "REVIEW_SCENARIO", "Scenario", scenario_id, {}, role=user.role)
    db.commit()
    return {"status": "REVIEWED"}


@router.post("/scenarios/{scenario_id}/approve-publish", response_model=PublishResponse)
def approve_and_publish(
    scenario_id: str,
    body: ApprovalRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    """Approve optimization run and publish changes."""
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(404, "Scenario not found")
    if scenario.status not in ("SIMULATED", "REVIEWED"):
        raise HTTPException(400, f"Cannot publish scenario in status: {scenario.status}")

    run = db.query(OptimizationRun).filter(OptimizationRun.id == body.run_id).first()
    if not run:
        raise HTTPException(404, "Optimization run not found")
    if run.scenario_id != scenario_id:
        raise HTTPException(400, "Run does not belong to this scenario")
    if run.status == "INFEASIBLE":
        raise HTTPException(400, "Cannot publish infeasible result")

    # Stale version check (unconditional - base_version_id should always be set)
    latest_version = db.query(PublishedVersion).order_by(
        PublishedVersion.version_no.desc()
    ).first()
    current_version_id = latest_version.id if latest_version else None
    current_version_no = latest_version.version_no if latest_version else 0

    if scenario.base_version_id != current_version_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stale version: campus state has changed since scenario creation"
        )

    # Create approval
    approval = Approval(
        id=f"appr_{uuid.uuid4().hex[:10]}",
        scenario_id=scenario_id,
        run_id=run.id,
        decided_by=user.id,
        decision="APPROVED",
        comment=body.comment,
        decided_at=get_now(),
    )
    db.add(approval)

    # Create published version
    new_version_no = current_version_no + 1
    version = PublishedVersion(
        id=f"ver_{uuid.uuid4().hex[:10]}",
        scenario_id=scenario_id,
        version_no=new_version_no,
        run_id=run.id,
        published_by=user.id,
        summary=f"{scenario.name} - {run.option_label}",
        published_at=get_now(),
    )
    db.add(version)
    db.flush()

    # Apply session overrides from assignments
    overrides_created = 0
    assignments = run.assignments or {}
    from app.models.schedule import TimetableEntry
    from app.models.campus import Room

    rooms_map = {r.id: r for r in db.query(Room).all()}

    for entry_id, new_room_id in assignments.items():
        entry = db.query(TimetableEntry).filter(TimetableEntry.id == entry_id).first()
        if entry and new_room_id != entry.base_room_id:
            old_room = rooms_map.get(entry.base_room_id)
            new_room = rooms_map.get(new_room_id)
            explanation = (run.explanations or {}).get(entry_id, "")

            override = SessionOverride(
                id=f"ovr_{uuid.uuid4().hex[:10]}",
                entry_id=entry_id,
                date=get_now(),
                room_id=new_room_id,
                old_room_id=entry.base_room_id,
                version_id=version.id,
                reason=f"{scenario.name}: {explanation}",
                active=True,
            )
            db.add(override)
            overrides_created += 1

    # Create notifications for affected sections/faculty
    notifications_created = 0
    sections_notified = set()
    faculty_notified = set()

    for entry_id, new_room_id in assignments.items():
        entry = db.query(TimetableEntry).filter(TimetableEntry.id == entry_id).first()
        if not entry:
            continue
        if new_room_id == entry.base_room_id:
            continue

        old_room = rooms_map.get(entry.base_room_id)
        new_room = rooms_map.get(new_room_id)
        old_code = old_room.code if old_room else "?"
        new_code = new_room.code if new_room else "?"

        if entry.section_id not in sections_notified:
            notif = Notification(
                id=f"notif_{uuid.uuid4().hex[:10]}",
                audience_type="SECTION",
                audience_id=entry.section_id,
                type="ROOM_CHANGED",
                title="Classroom Changed",
                body=f"Your class has been moved from {old_code} to {new_code}. Reason: {scenario.name}",
                payload={"entry_id": entry_id, "old_room": old_code, "new_room": new_code,
                         "version_id": version.id},
                created_at=get_now(),
            )
            db.add(notif)
            sections_notified.add(entry.section_id)
            notifications_created += 1

        if entry.faculty_id and entry.faculty_id not in faculty_notified:
            notif = Notification(
                id=f"notif_{uuid.uuid4().hex[:10]}",
                audience_type="FACULTY",
                audience_id=entry.faculty_id,
                type="ROOM_CHANGED",
                title="Teaching Room Changed",
                body=f"Room changed from {old_code} to {new_code}. Reason: {scenario.name}",
                payload={"entry_id": entry_id, "old_room": old_code, "new_room": new_code},
                created_at=get_now(),
            )
            db.add(notif)
            faculty_notified.add(entry.faculty_id)
            notifications_created += 1

    scenario.status = "PUBLISHED"
    log_audit(db, user.id, "APPROVE_PUBLISH", "PublishedVersion", version.id,
              {"scenario": scenario.name, "version_no": new_version_no,
               "overrides": overrides_created}, role=user.role)
    db.commit()

    return PublishResponse(
        version_id=version.id,
        version_no=new_version_no,
        summary=version.summary,
        overrides_created=overrides_created,
        notifications_created=notifications_created,
    )


@router.post("/scenarios/{scenario_id}/reject")
def reject_scenario(
    scenario_id: str,
    body: ApprovalRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    """Reject a scenario."""
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(404, "Scenario not found")

    approval = Approval(
        id=f"appr_{uuid.uuid4().hex[:10]}",
        scenario_id=scenario_id,
        run_id=body.run_id,
        decided_by=user.id,
        decision="REJECTED",
        comment=body.comment,
        decided_at=get_now(),
    )
    db.add(approval)
    scenario.status = "REJECTED"
    db.commit()
    return {"status": "REJECTED"}


# ------------- Versions --------------------------------------------------------

@router.get("/versions", response_model=List[VersionResponse])
def list_versions(db: Session = Depends(get_db), user: User = Depends(require_roles(["MANAGEMENT"]))):
    """List all published versions (Management only)."""
    versions = db.query(PublishedVersion).order_by(PublishedVersion.version_no.desc()).all()
    result = []
    for v in versions:
        scenario = db.query(Scenario).filter(Scenario.id == v.scenario_id).first()
        result.append(VersionResponse(
            id=v.id,
            version_no=v.version_no,
            scenario_id=v.scenario_id,
            scenario_name=scenario.name if scenario else None,
            published_by=v.published_by,
            published_at=v.published_at,
            summary=v.summary,
            reverted=v.reverted,
        ))
    return result


@router.post("/versions/{version_id}/revert")
def revert_version(
    version_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(["MANAGEMENT"])),
):
    """Revert a published version."""
    version = db.query(PublishedVersion).filter(PublishedVersion.id == version_id).first()
    if not version:
        raise HTTPException(404, "Version not found")
    if version.reverted:
        raise HTTPException(400, "Version already reverted")

    # Deactivate overrides
    overrides = db.query(SessionOverride).filter(
        SessionOverride.version_id == version_id
    ).all()
    for ov in overrides:
        ov.active = False

    version.reverted = True

    affected_entry_ids = {override.entry_id for override in overrides}
    affected_entries = db.query(TimetableEntry).filter(
        TimetableEntry.id.in_(affected_entry_ids)
    ).all() if affected_entry_ids else []
    notified_sections = set()
    notified_faculty = set()
    for entry in affected_entries:
        audiences = []
        if entry.section_id and entry.section_id not in notified_sections:
            audiences.append(("SECTION", entry.section_id, notified_sections))
        if entry.faculty_id and entry.faculty_id not in notified_faculty:
            audiences.append(("FACULTY", entry.faculty_id, notified_faculty))
        for audience_type, audience_id, notified in audiences:
            db.add(Notification(
                id=f"notif_{uuid.uuid4().hex[:10]}",
                audience_type=audience_type,
                audience_id=audience_id,
                type="VERSION_REVERTED",
                title=f"Version {version.version_no} Reverted",
                body="Published timetable changes affecting you have been reverted by management.",
                payload={"version_id": version_id, "entry_id": entry.id},
                created_at=get_now(),
            ))
            notified.add(audience_id)

    log_audit(db, user.id, "REVERT_VERSION", "PublishedVersion", version_id,
              {"version_no": version.version_no}, role=user.role)
    db.commit()
    return {"ok": True, "reverted_overrides": len(overrides)}


# ------------- Notifications ---------------------------------------------------

@router.get("/notifications", response_model=List[NotificationResponse])
def get_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get notifications for current user."""
    from app.models.workflow import NotificationRead
    from app.models.academic import Student, Faculty

    audience_conditions = [
        and_(
            Notification.audience_type == "USER",
            Notification.audience_id == user.id,
        ),
        and_(
            Notification.audience_type == "ROLE",
            Notification.audience_id.in_([user.role, "ALL"]),
        ),
    ]

    if user.role == "STUDENT":
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if student and student.section_id:
            audience_conditions.append(and_(
                Notification.audience_type == "SECTION",
                Notification.audience_id == student.section_id,
            ))

    if user.role == "FACULTY":
        faculty = db.query(Faculty).filter(Faculty.user_id == user.id).first()
        if faculty:
            audience_conditions.append(and_(
                Notification.audience_type == "FACULTY",
                Notification.audience_id == faculty.id,
            ))

    notifications = db.query(Notification).filter(
        or_(*audience_conditions)
    ).order_by(Notification.created_at.desc()).limit(50).all()

    # Check read status
    read_ids = set()
    reads = db.query(NotificationRead).filter(
        NotificationRead.user_id == user.id,
        NotificationRead.notification_id.in_([n.id for n in notifications]),
    ).all()
    read_ids = {r.notification_id for r in reads}

    return [NotificationResponse(
        id=n.id, type=n.type, title=n.title, body=n.body,
        payload=n.payload, created_at=n.created_at,
        read=n.id in read_ids,
    ) for n in notifications]


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark notification as read."""
    from app.models.workflow import NotificationRead
    existing = db.query(NotificationRead).filter(
        NotificationRead.notification_id == notification_id,
        NotificationRead.user_id == user.id,
    ).first()
    if not existing:
        db.add(NotificationRead(
            notification_id=notification_id,
            user_id=user.id,
            read_at=get_now(),
        ))
        db.commit()
    return {"ok": True}


# ------------- Helper -----------------------------------------------------------

def _scenario_response(scenario: Scenario, db: Session) -> ScenarioResponse:
    changes = db.query(ScenarioChange).filter(
        ScenarioChange.scenario_id == scenario.id
    ).all()
    return ScenarioResponse(
        id=scenario.id,
        name=scenario.name,
        category=scenario.category,
        status=scenario.status,
        created_by=scenario.created_by,
        created_at=scenario.created_at,
        base_version_id=scenario.base_version_id,
        changes=[{"type": c.type, "payload": c.payload} for c in changes],
    )
