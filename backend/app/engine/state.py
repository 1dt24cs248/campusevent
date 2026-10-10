"""Scenario state engine - applies scenario changes as temporary overlays."""
import uuid
from datetime import time
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from app.engine.slots import (
    PERIOD_SLOTS, SLOT_INDEX, WEEKDAYS, get_slots_for_day,
    time_window_affects_slot,
)
from app.engine.optimizer import AllocationOptimizer, EntryInfo, RoomInfo, SolverResult


@dataclass
class ScenarioState:
    """In-memory snapshot of campus state with scenario delta applied."""
    entries: List[EntryInfo]
    rooms: List[RoomInfo]
    unavailable_rooms: Set[str]
    occupied_slots: Dict[Tuple[int, str], Set[str]]
    affected_entry_ids: Set[str]
    change_descriptions: List[str]
    unavailable_room_slots: Dict[Tuple[int, str], Set[str]] = field(default_factory=dict)


def build_base_state(db: Session) -> ScenarioState:
    """Build the base campus state from the database."""
    from app.models.campus import Room, Floor
    from app.models.academic import Section, Subject
    from app.models.schedule import TimetableEntry

    # Load rooms
    db_rooms = db.query(Room).all()
    floors = {f.id: f for f in db.query(Floor).all()}
    rooms = []
    for r in db_rooms:
        floor = floors.get(r.floor_id)
        rooms.append(RoomInfo(
            id=r.id, code=r.code, resource_type=r.resource_type,
            capacity=r.capacity,
            floor_level=floor.level if floor else 0,
            floor_id=r.floor_id,
            lab_kind=r.lab_kind, facilities=r.facilities or [],
            is_spare=r.is_spare or False,
            block_id=r.block_id,
            status=r.status or "ACTIVE",
            allocatable_for_classes=bool(r.allocatable_for_classes),
            capacity_provenance=r.capacity_provenance,
        ))

    # Load sections
    sections = {s.id: s for s in db.query(Section).all()}
    subjects = {subject.id: subject for subject in db.query(Subject).all()}

    # Load timetable entries
    db_entries = db.query(TimetableEntry).all()
    entries = []
    occupied_slots: Dict[Tuple[int, str], Set[str]] = {}

    for te in db_entries:
        sec = sections.get(te.section_id)
        subject = subjects.get(te.subject_id)
        required_facilities = set(te.required_facilities or [])
        if subject:
            required_facilities.update(subject.required_facilities or [])
        entry = EntryInfo(
            id=te.id, section_id=te.section_id,
            section_name=sec.code if sec else te.section_id,
            strength=sec.strength if sec else None,
            weekday=te.weekday, start_slot=te.start_slot,
            duration_slots=te.duration_slots or 1, kind=te.kind,
            required_room_type=te.required_room_type or (
                "LAB" if te.kind == "LAB" else "CLASSROOM"
            ),
            required_lab_kind=te.required_lab_kind or (subject.lab_kind if subject else None),
            required_facilities=sorted(required_facilities),
            base_room_id=te.base_room_id,
            home_room_id=sec.home_room_id if sec else None,
            faculty_id=te.faculty_id,
            subject_id=te.subject_id,
        )
        entries.append(entry)

        # Track room occupancy
        if te.base_room_id:
            start_idx = SLOT_INDEX.get(te.start_slot)
            for d in range(max(te.duration_slots or 1, 1)):
                if start_idx is None:
                    break
                idx = start_idx + d
                if idx < len(PERIOD_SLOTS) and PERIOD_SLOTS[idx] in get_slots_for_day(te.weekday):
                    key = (te.weekday, PERIOD_SLOTS[idx])
                    if key not in occupied_slots:
                        occupied_slots[key] = set()
                    occupied_slots[key].add(te.base_room_id)

    return ScenarioState(
        entries=entries, rooms=rooms, unavailable_rooms=set(),
        occupied_slots=occupied_slots, affected_entry_ids=set(),
        change_descriptions=[],
    )


def apply_scenario_changes(state: ScenarioState, changes: List[Dict]) -> ScenarioState:
    """Apply scenario changes to a state snapshot (non-destructive)."""
    from fastapi import HTTPException

    new_state = ScenarioState(
        entries=list(state.entries),
        rooms=list(state.rooms),
        unavailable_rooms=set(state.unavailable_rooms),
        occupied_slots={k: set(v) for k, v in state.occupied_slots.items()},
        affected_entry_ids=set(state.affected_entry_ids),
        change_descriptions=list(state.change_descriptions),
        unavailable_room_slots={
            key: set(room_ids)
            for key, room_ids in state.unavailable_room_slots.items()
        },
    )

    for change in changes:
        ctype = change.get("type", "")
        payload = change.get("payload", {})

        if ctype == "ROOM_UNAVAILABLE":
            _apply_room_unavailable(new_state, payload)
        elif ctype == "FLOOR_UNAVAILABLE":
            _apply_floor_unavailable(new_state, payload)
        elif ctype == "RESERVE_ROOMS":
            _apply_room_unavailable(new_state, payload)  # Same logic
        elif ctype == "CHANGE_STRENGTH":
            _apply_change_strength(new_state, payload)
        elif ctype == "CHANGE_ROOM_CAPACITY":
            _apply_change_room_capacity(new_state, payload)
        elif ctype == "ADD_SECTION":
            _apply_add_section(new_state, payload)
        elif ctype == "MOVE_CLASS":
            _apply_move_class(new_state, payload)
        elif ctype == "STRESS_TEST":
            _apply_stress_test(new_state, payload)
        else:
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported scenario change type: {ctype or '(empty)'}",
            )

    return new_state


def _apply_room_unavailable(state: ScenarioState, payload: Dict):
    """Mark rooms as unavailable and identify affected entries."""
    from fastapi import HTTPException

    raw_room_ids = payload.get("room_ids")
    if not isinstance(raw_room_ids, list):
        raise HTTPException(status_code=422, detail="room_ids must be a list of existing room IDs.")
    if any(not isinstance(room_id, str) or not room_id for room_id in raw_room_ids):
        raise HTTPException(status_code=422, detail="room_ids must contain non-empty room ID strings.")
    room_ids = set(raw_room_ids)
    if not room_ids:
        raise HTTPException(
            status_code=422,
            detail="ROOM_UNAVAILABLE requires at least one existing room ID.",
        )
    existing_room_ids = {room.id for room in state.rooms}
    unknown_room_ids = room_ids - existing_room_ids
    if unknown_room_ids:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown room IDs: {', '.join(sorted(unknown_room_ids))}.",
        )

    time_from = payload.get("time_from")
    time_to = payload.get("time_to")
    if (time_from is None) != (time_to is None):
        raise HTTPException(
            status_code=422,
            detail="Provide both time_from and time_to, or omit both for a full-day closure.",
        )
    try:
        if time_from is not None:
            t_from = time.fromisoformat(time_from) if isinstance(time_from, str) else time_from
            t_to = time.fromisoformat(time_to) if isinstance(time_to, str) else time_to
        else:
            t_from, t_to = time(0, 0), time(23, 59, 59)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Closure times must use HH:MM format.") from exc
    if t_to <= t_from:
        raise HTTPException(status_code=422, detail="time_to must be later than time_from.")

    requested_days = payload.get("weekdays")
    if requested_days is None and "weekday" in payload:
        requested_days = [payload["weekday"]]
    if requested_days is None:
        weekdays = set(WEEKDAYS)
    else:
        if not isinstance(requested_days, list) or not requested_days:
            raise HTTPException(status_code=422, detail="weekdays must be a non-empty list.")
        weekdays = set()
        names = {name.lower(): day for day, name in WEEKDAYS.items()}
        for day in requested_days:
            if isinstance(day, str):
                day = names.get(day.strip().lower())
            if not isinstance(day, int) or day not in WEEKDAYS:
                raise HTTPException(status_code=422, detail="Closure weekdays must be Monday through Saturday.")
            weekdays.add(day)

    closed_slots = {
        slot for slot in PERIOD_SLOTS
        if time_window_affects_slot(t_from, t_to, slot)
    }
    for weekday in weekdays:
        for slot in closed_slots:
            state.unavailable_room_slots.setdefault((weekday, slot), set()).update(room_ids)
    if weekdays == set(WEEKDAYS) and closed_slots == set(PERIOD_SLOTS):
        state.unavailable_rooms.update(room_ids)

    # Find affected entries
    room_info = {r.id: r for r in state.rooms}
    affected_count = 0
    for entry in state.entries:
        if entry.base_room_id not in room_ids or entry.weekday not in weekdays:
            continue
        start_idx = SLOT_INDEX.get(entry.start_slot)
        if start_idx is None:
            continue
        entry_slots = {
            PERIOD_SLOTS[start_idx + offset]
            for offset in range(max(entry.duration_slots or 1, 1))
            if (
                start_idx + offset < len(PERIOD_SLOTS)
                and PERIOD_SLOTS[start_idx + offset] in get_slots_for_day(entry.weekday)
            )
        }
        if entry_slots & closed_slots:
            state.affected_entry_ids.add(entry.id)
            affected_count += 1

    room_codes = [
        room_info[rid].code for rid in sorted(room_ids) if rid in room_info
    ]
    day_label = (
        "all weekdays"
        if weekdays == set(WEEKDAYS)
        else ", ".join(WEEKDAYS[day] for day in sorted(weekdays))
    )
    state.change_descriptions.append(
        f"Rooms {', '.join(room_codes)} marked unavailable on {day_label} "
        f"({t_from}-{t_to}). {affected_count} classes affected."
    )


def _apply_floor_unavailable(state: ScenarioState, payload: Dict):
    """Expand floor unavailability to all rooms on that floor."""
    from fastapi import HTTPException
    
    floor_id = payload.get("floor_id")
    floor_level = payload.get("floor_level")
    
    # Require explicit floor identifier
    if not floor_id and floor_level is None:
        raise HTTPException(
            status_code=400,
            detail="FLOOR_UNAVAILABLE requires either 'floor_id' or 'floor_level' in payload"
        )
    
    if floor_id:
        floor_rooms = [r.id for r in state.rooms if r.floor_id == floor_id]
        if not floor_rooms:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown floor identifier or no allocatable rooms on floor: {floor_id}",
            )
    else:
        try:
            requested_level = int(floor_level)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid floor level: {floor_level}",
            )
        floor_rooms = [r.id for r in state.rooms if r.floor_level == requested_level]

    if not floor_rooms:
        raise HTTPException(
            status_code=400,
            detail=f"No allocatable rooms found for floor level: {floor_level}",
        )

    payload_copy = dict(payload)
    payload_copy["room_ids"] = floor_rooms
    _apply_room_unavailable(state, payload_copy)


def _apply_change_strength(state: ScenarioState, payload: Dict):
    """Change section strength - affects capacity requirements."""
    from fastapi import HTTPException

    section_id = payload.get("section_id")
    new_strength = payload.get("new_strength")
    if not section_id or not isinstance(new_strength, int) or new_strength < 1:
        raise HTTPException(
            status_code=422,
            detail="CHANGE_STRENGTH requires a section_id and a positive new_strength.",
        )

    matching_entries = [entry for entry in state.entries if entry.section_id == section_id]
    if not matching_entries:
        raise HTTPException(
            status_code=422,
            detail=f"No scheduled timetable entries exist for section {section_id}.",
        )
    for entry in matching_entries:
        entry.strength = new_strength
        state.affected_entry_ids.add(entry.id)

    state.change_descriptions.append(
        f"Section {section_id} strength changed to {new_strength}."
    )


def _apply_change_room_capacity(state: ScenarioState, payload: Dict):
    """Apply a temporary room-capacity override to the scenario snapshot."""
    from fastapi import HTTPException

    room_id = payload.get("room_id")
    new_capacity = payload.get("new_capacity")
    room = next((candidate for candidate in state.rooms if candidate.id == room_id), None)
    if room is None:
        raise HTTPException(status_code=422, detail="CHANGE_ROOM_CAPACITY requires an existing room_id.")
    if not isinstance(new_capacity, int) or new_capacity < 1:
        raise HTTPException(status_code=422, detail="new_capacity must be a positive integer.")

    room.capacity = new_capacity
    for entry in state.entries:
        if entry.base_room_id == room_id:
            state.affected_entry_ids.add(entry.id)
    state.change_descriptions.append(
        f"Room {room.code} capacity changed to {new_capacity} for this simulation."
    )


def _apply_add_section(state: ScenarioState, payload: Dict):
    """Add a new section by cloning a reference section's pattern."""
    name = payload.get("name", "NEW-SEC")
    strength = payload.get("strength", 60)
    clone_from = payload.get("clone_pattern_from_section_id")

    if clone_from:
        ref_entries = [e for e in state.entries if e.section_id == clone_from]
        for re in ref_entries:
            new_entry = EntryInfo(
                id=f"tt_new_{uuid.uuid4().hex[:8]}",
                section_id=f"sec_new_{uuid.uuid4().hex[:6]}",
                section_name=name,
                strength=strength,
                weekday=re.weekday,
                start_slot=re.start_slot,
                duration_slots=re.duration_slots,
                kind=re.kind,
                required_room_type=re.required_room_type,
                required_lab_kind=re.required_lab_kind,
                required_facilities=re.required_facilities,
                base_room_id=None,  # Needs allocation
                home_room_id=None,
                faculty_id=None,
                subject_id=re.subject_id,
            )
            state.entries.append(new_entry)
            state.affected_entry_ids.add(new_entry.id)

    state.change_descriptions.append(f"New section '{name}' added with strength {strength}.")


def _apply_move_class(state: ScenarioState, payload: Dict):
    """Move a specific class to a new time slot."""
    from fastapi import HTTPException

    entry_id = payload.get("entry_id")
    new_slot = payload.get("new_start_slot")
    if not entry_id or new_slot not in PERIOD_SLOTS:
        raise HTTPException(
            status_code=422,
            detail="MOVE_CLASS requires an existing entry_id and a P1-P7 new_start_slot.",
        )

    for entry in state.entries:
        if entry.id == entry_id:
            entry.start_slot = new_slot
            state.affected_entry_ids.add(entry.id)
            state.change_descriptions.append(
                f"Class {entry.section_name} moved to slot {new_slot}."
            )
            return
    raise HTTPException(status_code=422, detail=f"Unknown timetable entry: {entry_id}.")


def _apply_stress_test(state: ScenarioState, payload: Dict):
    """Close k busiest rooms to test campus capacity limits."""
    from fastapi import HTTPException

    k = payload.get("k", 5)
    if not isinstance(k, int) or k < 1:
        raise HTTPException(status_code=422, detail="STRESS_TEST k must be a positive integer.")

    # Count how many entries use each room
    room_usage = {}
    for entry in state.entries:
        if entry.base_room_id:
            room_usage[entry.base_room_id] = room_usage.get(entry.base_room_id, 0) + 1

    # Sort by usage descending, pick top k
    sorted_rooms = sorted(room_usage.items(), key=lambda x: (-x[1], x[0]))
    rooms_to_close = [rid for rid, _ in sorted_rooms[:k]]
    if not rooms_to_close:
        state.change_descriptions.append(
            f"Stress test: no timetable rooms are currently in use; 0 classes affected."
        )
        return

    payload_copy = {"room_ids": rooms_to_close}
    _apply_room_unavailable(state, payload_copy)
    room_codes = [
        room.code for room in state.rooms if room.id in set(rooms_to_close)
    ]
    selected = ", ".join(room_codes) if room_codes else "none"
    state.change_descriptions.append(
        f"Stress test: requested closure of {k} busiest rooms; "
        f"{len(rooms_to_close)} occupied rooms selected ({selected})."
    )


def run_scenario_simulation(
    db: Session,
    changes: List[Dict],
    strategies: List[str] = None,
    time_limit_sec: int = 8,
) -> Tuple[ScenarioState, List[SolverResult]]:
    """Run a complete scenario simulation end-to-end."""
    # Build base state
    base_state = build_base_state(db)
    before_metrics = _schedule_metrics(base_state.entries, base_state.rooms)
    before_room_occupancy = _room_occupancy_metrics(base_state.entries, base_state.rooms)

    # Apply scenario changes
    scenario_state = apply_scenario_changes(base_state, changes)
    stress_condition = next(
        (description.removeprefix("Stress test: ").rstrip(".")
         for description in scenario_state.change_descriptions
         if description.startswith("Stress test: ")),
        None,
    )

    # Get only affected entries that need reallocation
    affected_entries = [e for e in scenario_state.entries if e.id in scenario_state.affected_entry_ids]

    if not affected_entries:
        return scenario_state, [SolverResult(
            status="FEASIBLE",
            option_label="No changes needed",
            strategy="NONE",
            metrics={
                "total_entries": 0,
                "assigned": 0,
                "unresolved": 0,
                "room_changes": 0,
                "conflict_count_before": before_metrics["conflict_count"],
                "conflict_count_after": before_metrics["conflict_count"],
                "utilization_before": before_metrics["utilization_ratio"],
                "utilization_after": before_metrics["utilization_ratio"],
                "capacity_pressure_before": before_metrics["capacity_pressure_classes"],
                "capacity_pressure_after": before_metrics["capacity_pressure_classes"],
                "room_occupancy_before": before_room_occupancy,
                "room_occupancy_after": before_room_occupancy,
                "utilization_basis": "enrolled seats / allocated room seats; ratio, not percentage",
                "capacity_pressure_basis": "scheduled classes without a room or enough capacity",
                **({"stress_condition": stress_condition} if stress_condition else {}),
            },
        )]

    # Build occupancy excluding affected entries
    occupied = {}
    for entry in scenario_state.entries:
        if entry.id in scenario_state.affected_entry_ids or not entry.base_room_id:
            continue
        start_idx = SLOT_INDEX.get(entry.start_slot)
        if start_idx is None:
            continue
        for offset in range(max(entry.duration_slots or 1, 1)):
            slot_index = start_idx + offset
            if (
                slot_index >= len(PERIOD_SLOTS)
                or PERIOD_SLOTS[slot_index] not in get_slots_for_day(entry.weekday)
            ):
                break
            occupied.setdefault((entry.weekday, PERIOD_SLOTS[slot_index]), set()).add(
                entry.base_room_id
            )

    affected_slot_sets = {
        entry.id: _entry_weekly_slots(entry)
        for entry in affected_entries
    }
    hard_conflicts: Dict[str, List[str]] = {}
    for entry in affected_entries:
        entry_slots = affected_slot_sets[entry.id]
        for other in scenario_state.entries:
            if other.id == entry.id or not entry_slots.intersection(
                affected_slot_sets.get(other.id, _entry_weekly_slots(other))
            ):
                continue
            if entry.faculty_id and entry.faculty_id == other.faculty_id:
                hard_conflicts.setdefault(entry.id, []).append(
                    f"Faculty conflict with timetable entry {other.id}."
                )
            if entry.section_id and entry.section_id == other.section_id:
                hard_conflicts.setdefault(entry.id, []).append(
                    f"Section conflict with timetable entry {other.id}."
                )

    # Run optimizer
    optimizer = AllocationOptimizer(
        entries=affected_entries,
        rooms=scenario_state.rooms,
        unavailable_rooms=scenario_state.unavailable_rooms,
        occupied_slots=occupied,
        unavailable_room_slots=scenario_state.unavailable_room_slots,
        hard_conflicts=hard_conflicts,
        time_limit_sec=time_limit_sec,
    )

    results = optimizer.solve_multiple(strategies=strategies)

    for result in results:
        final_room_assignments = {
            entry.id: entry.base_room_id for entry in scenario_state.entries
        }
        final_room_assignments.update(result.assignments)
        for item in result.unresolved:
            final_room_assignments[item.get("entry_id")] = None
        after_metrics = _schedule_metrics(
            scenario_state.entries,
            scenario_state.rooms,
            final_room_assignments,
        )
        after_room_occupancy = _room_occupancy_metrics(
            scenario_state.entries,
            scenario_state.rooms,
            final_room_assignments,
        )
        result.metrics.update({
            "conflict_count_before": before_metrics["conflict_count"],
            "conflict_count_after": after_metrics["conflict_count"],
            "utilization_before": before_metrics["utilization_ratio"],
            "utilization_after": after_metrics["utilization_ratio"],
            "capacity_pressure_before": before_metrics["capacity_pressure_classes"],
            "capacity_pressure_after": after_metrics["capacity_pressure_classes"],
            "room_occupancy_before": before_room_occupancy,
            "room_occupancy_after": after_room_occupancy,
            "utilization_basis": "enrolled seats / allocated room seats; ratio, not percentage",
            "capacity_pressure_basis": "scheduled classes without a room or enough capacity",
            **({"stress_condition": stress_condition} if stress_condition else {}),
        })
        if result.unresolved:
            result.recovery = _generate_recovery(result.unresolved, scenario_state)

    return scenario_state, results


def _entry_weekly_slots(entry: EntryInfo) -> Set[Tuple[int, str]]:
    start_idx = SLOT_INDEX.get(entry.start_slot)
    if start_idx is None or entry.weekday not in WEEKDAYS:
        return set()
    slots = get_slots_for_day(entry.weekday)
    return {
        (entry.weekday, PERIOD_SLOTS[start_idx + offset])
        for offset in range(max(entry.duration_slots or 1, 1))
        if (
            start_idx + offset < len(PERIOD_SLOTS)
            and PERIOD_SLOTS[start_idx + offset] in slots
        )
    }


def _room_occupancy_metrics(
    entries: List[EntryInfo],
    rooms: List[RoomInfo],
    room_assignments: Dict[str, Optional[str]] = None,
) -> Dict[str, Any]:
    assignments = room_assignments if room_assignments is not None else {
        entry.id: entry.base_room_id for entry in entries
    }
    occupied: Dict[str, Set[Tuple[int, str]]] = {}
    for entry in entries:
        room_id = assignments.get(entry.id)
        if room_id:
            occupied.setdefault(room_id, set()).update(_entry_weekly_slots(entry))

    room_by_id = {room.id: room for room in rooms}
    total_slots = sum(len(slots) for slots in occupied.values())
    candidate_rooms = [
        room for room in rooms
        if room.allocatable_for_classes and (room.status or "").upper() == "ACTIVE"
    ]
    weekly_periods_per_room = sum(len(get_slots_for_day(day)) for day in WEEKDAYS)
    room_details = [{
        "room_id": room.id,
        "room_code": room.code,
        "occupied_periods": len(occupied.get(room.id, set())),
        "available_periods": weekly_periods_per_room,
        "capacity": room.capacity,
        "capacity_provenance": room.capacity_provenance,
    } for room in sorted(candidate_rooms, key=lambda value: (value.floor_level, value.code, value.id))]
    return {
        "occupied_room_periods": total_slots,
        "available_room_periods": len(candidate_rooms) * weekly_periods_per_room,
        "rooms_in_use": sum(bool(occupied.get(room.id)) for room in candidate_rooms),
        "rooms_with_unknown_capacity": sum(room.capacity is None for room in candidate_rooms),
        "by_room": room_details,
    }


def _schedule_metrics(
    entries: List[EntryInfo],
    rooms: List[RoomInfo],
    room_assignments: Dict[str, Optional[str]] = None,
) -> Dict[str, Any]:
    """Measure actual scheduled seat ratios, capacity pressure, and room overlaps."""
    room_by_id = {room.id: room for room in rooms}
    assignments = room_assignments if room_assignments is not None else {
        entry.id: entry.base_room_id for entry in entries
    }
    occupied: Dict[Tuple[int, str, str], int] = {}
    student_seats = 0
    allocated_seats = 0
    capacity_pressure = 0
    conflicts = 0

    from app.engine.slots import SLOT_INDEX
    for entry in entries:
        room_id = assignments.get(entry.id)
        room = room_by_id.get(room_id)
        if (
            room is None
            or room.capacity is None
            or entry.strength is None
            or room.capacity < entry.strength
        ):
            capacity_pressure += 1
        if room is None:
            continue

        student_seats += entry.strength or 0
        allocated_seats += room.capacity or 0
        start_idx = SLOT_INDEX.get(entry.start_slot)
        if start_idx is None:
            continue
        day_slots = set(get_slots_for_day(entry.weekday))
        for offset in range(max(entry.duration_slots or 1, 1)):
            slot_idx = start_idx + offset
            if slot_idx >= len(PERIOD_SLOTS) or PERIOD_SLOTS[slot_idx] not in day_slots:
                break
            key = (entry.weekday, PERIOD_SLOTS[slot_idx], room_id)
            conflicts += occupied.get(key, 0)
            occupied[key] = occupied.get(key, 0) + 1

    return {
        "conflict_count": conflicts,
        "capacity_pressure_classes": capacity_pressure,
        "utilization_ratio": (
            round(student_seats / allocated_seats, 4) if allocated_seats else 0.0
        ),
    }


def _generate_recovery(unresolved: List[Dict], state: ScenarioState) -> List[Dict]:
    """Generate actionable recovery suggestions for unresolved entries."""
    suggestions = []
    for item in unresolved:
        entry_id = item["entry_id"]
        entry = next((e for e in state.entries if e.id == entry_id), None)
        if not entry:
            continue

        # Check rooms that are close to fitting
        near_miss = []
        for room in state.rooms:
            if room.id in state.unavailable_rooms:
                continue
            if (
                room.resource_type == "CLASSROOM"
                and entry.required_room_type == "CLASSROOM"
                and entry.strength is not None
                and room.capacity is not None
            ):
                diff = entry.strength - room.capacity
                if 0 < diff <= 10:
                    near_miss.append(f"Room {room.code} (cap {room.capacity}, short by {diff})")

        if near_miss:
            suggestions.append({
                "type": "RELAX_CAPACITY",
                "description": f"If attendance factor is reduced, these rooms could work: {', '.join(near_miss[:3])}",
            })

        # Suggest time shift
        suggestions.append({
            "type": "TIME_SHIFT",
            "description": f"Try shifting {entry.section_name}'s class to a different period where more rooms are available",
        })

    return suggestions
