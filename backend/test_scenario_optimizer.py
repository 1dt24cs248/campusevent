"""Focused solver and scenario-overlay tests with in-memory data only."""

import json
import re
from pathlib import Path

import pytest

from app.engine.optimizer import AllocationOptimizer, EntryInfo, RoomInfo
from app.engine.state import ScenarioState, _generate_recovery, apply_scenario_changes


BLOCK_A_INVENTORY = json.loads(
    (Path(__file__).resolve().parents[1] / "data" / "blockA_master.json").read_text(
        encoding="utf-8"
    )
)


def _inventory_rooms(floor_key):
    floor_levels = {"basement": -1, "ground": 0}
    result = []
    for source in BLOCK_A_INVENTORY["rooms"][floor_key]:
        room_id = f"inventory_{re.sub(r'[^a-z0-9]+', '_', source['code'].lower()).strip('_')}"
        result.append(RoomInfo(
            id=room_id,
            code=source["code"],
            resource_type=source["resource_type"],
            capacity=source["capacity"],
            floor_level=floor_levels[floor_key],
            floor_id=f"floor_A_{floor_key}",
            lab_kind=source["lab_kind"],
            facilities=source["facilities"],
            block_id="block_A",
            allocatable_for_classes=source["allocatable_for_classes"],
            capacity_provenance=source["capacity_provenance"],
        ))
    return result


def _entry(
    entry_id,
    *,
    weekday=0,
    slot="P1",
    strength=20,
    section="section-a",
    faculty=None,
    facilities=None,
):
    return EntryInfo(
        id=entry_id,
        section_id=section,
        section_name=section,
        strength=strength,
        weekday=weekday,
        start_slot=slot,
        duration_slots=1,
        kind="THEORY",
        required_room_type="CLASSROOM",
        required_facilities=facilities or [],
        base_room_id=None,
        faculty_id=faculty,
    )


def _room(
    room_id,
    *,
    capacity=40,
    facilities=None,
    block="block-a",
    capacity_provenance="PROVIDED",
):
    return RoomInfo(
        id=room_id,
        code=room_id.upper(),
        resource_type="CLASSROOM",
        capacity=capacity,
        floor_level=1,
        facilities=facilities or [],
        block_id=block,
        capacity_provenance=capacity_provenance,
    )


def test_solver_finds_joint_allocation_instead_of_greedy_dead_end():
    constrained = _entry("requires-projector", facilities=["PROJECTOR"])
    flexible = _entry("flexible", section="section-b")
    rooms = [
        _room("projector-room", capacity=40, facilities=["PROJECTOR"]),
        _room("general-room", capacity=50),
    ]

    result = AllocationOptimizer([constrained, flexible], rooms).solve()

    assert result.status == "FEASIBLE"
    assert result.assignments == {
        "requires-projector": "projector-room",
        "flexible": "general-room",
    }


def test_solver_is_repeatable_and_rejects_unknown_capacity_or_out_of_block_rooms():
    entry = _entry("class")
    rooms = [
        _room("unknown-capacity", capacity=None),
        _room("other-block", block="block-b"),
        _room("valid", capacity=25),
    ]
    entry.base_room_id = "home"
    rooms.append(_room("home", capacity=30))

    first = AllocationOptimizer([entry], rooms).solve()
    second = AllocationOptimizer([entry], rooms).solve()

    assert first.status == "FEASIBLE"
    assert first.assignments == second.assignments
    assert first.assignments["class"] == "home"
    rejected = AllocationOptimizer([entry], rooms)._get_rejection_reasons(entry, [rooms[-1]])
    assert "room capacity is not recorded" in next(
        item["reasons"] for item in rejected if item["room"] == "UNKNOWN-CAPACITY"
    )
    assert "room is outside the affected block" in next(
        item["reasons"] for item in rejected if item["room"] == "OTHER-BLOCK"
    )


def test_solver_rejects_estimated_or_unrecorded_capacity_even_when_numeric_capacity_suffices():
    entry = _entry("needs-verified-capacity", strength=30)
    estimated = _room("estimated", capacity=60, capacity_provenance="ESTIMATED")
    unrecorded = _room("unrecorded", capacity=60, capacity_provenance=None)
    verified = _room("verified", capacity=60)
    verified.capacity_provenance = "PROVIDED"

    result = AllocationOptimizer([entry], [estimated, unrecorded]).solve()
    reasons = AllocationOptimizer([entry], [estimated, unrecorded])._get_rejection_reasons(
        entry, []
    )

    assert result.status == "PARTIAL"
    assert result.unresolved[0]["reason"] == "No compatible room available"
    assert any("ESTIMATED is not verified" in reason for room in reasons
               if room["room"] == "ESTIMATED" for reason in room["reasons"])
    assert any("provenance is not recorded" in reason for room in reasons
               if room["room"] == "UNRECORDED" for reason in room["reasons"])
    verified_result = AllocationOptimizer([entry], [verified]).solve()
    assert verified_result.assignments == {entry.id: verified.id}


def test_solver_rejects_invalid_saturday_period_and_timetable_conflict():
    entry = _entry("invalid-saturday", weekday=5, slot="P5")
    result = AllocationOptimizer([entry], [_room("room")]).solve()
    assert result.status == "PARTIAL"
    assert result.unresolved[0]["reason"] == "Invalid weekday, time slot, or class duration"

    conflicted = _entry("conflicted", faculty="faculty-a")
    conflict_result = AllocationOptimizer(
        [conflicted],
        [_room("room")],
        hard_conflicts={"conflicted": ["Faculty conflict with existing class."]},
    ).solve()
    assert conflict_result.status == "PARTIAL"
    assert "Faculty conflict" in conflict_result.unresolved[0]["reason"]


def test_closure_overlay_combines_rooms_and_only_affects_overlapping_weekday_slots():
    monday_p1 = _entry("monday-p1", slot="P1")
    monday_p2 = _entry("monday-p2", slot="P2")
    tuesday_p2 = _entry("tuesday-p2", weekday=1, slot="P2")
    monday_p1.base_room_id = "room-a"
    monday_p2.base_room_id = "room-a"
    tuesday_p2.base_room_id = "room-b"
    state = ScenarioState(
        entries=[monday_p1, monday_p2, tuesday_p2],
        rooms=[_room("room-a"), _room("room-b")],
        unavailable_rooms=set(),
        occupied_slots={},
        affected_entry_ids=set(),
        change_descriptions=[],
    )

    result = apply_scenario_changes(state, [
        {
            "type": "ROOM_UNAVAILABLE",
            "payload": {
                "room_ids": ["room-a"],
                "weekdays": [0],
                "time_from": "10:25",
                "time_to": "11:20",
            },
        },
        {
            "type": "ROOM_UNAVAILABLE",
            "payload": {"room_ids": ["room-b"], "weekday": 1},
        },
    ])

    assert result.affected_entry_ids == {"monday-p2", "tuesday-p2"}
    assert result.unavailable_room_slots[(0, "P2")] == {"room-a"}
    assert result.unavailable_room_slots[(1, "P1")] == {"room-b"}
    assert not result.unavailable_rooms


def test_all_weekday_eight_to_six_closure_matches_schedulable_overlapping_periods():
    scheduled = [
        _entry("monday-p1", weekday=0, slot="P1"),
        _entry("friday-p7", weekday=4, slot="P7"),
        _entry("saturday-p4", weekday=5, slot="P4"),
        _entry("saturday-p5-invalid", weekday=5, slot="P5"),
        _entry("monday-roomless", weekday=0, slot="P1"),
    ]
    for entry in scheduled[:-1]:
        entry.base_room_id = "room-a101"
    state = ScenarioState(
        entries=scheduled,
        rooms=[_room("room-a101")],
        unavailable_rooms=set(),
        occupied_slots={},
        affected_entry_ids=set(),
        change_descriptions=[],
    )

    changed = apply_scenario_changes(state, [{
        "type": "ROOM_UNAVAILABLE",
        "payload": {
            "room_ids": ["room-a101"],
            "weekdays": [0, 1, 2, 3, 4, 5],
            "time_from": "08:00",
            "time_to": "18:00",
        },
    }])

    assert changed.affected_entry_ids == {
        "monday-p1", "friday-p7", "saturday-p4",
    }
    assert changed.unavailable_room_slots[(5, "P5")] == {"room-a101"}
    assert scheduled[-1].id not in changed.affected_entry_ids


def test_closing_all_classrooms_on_a_floor_reallocates_together_and_preserves_other_room_types():
    classrooms = [
        RoomInfo(
            id=f"classroom-{index}",
            code=f"A30{index}",
            resource_type="CLASSROOM",
            capacity=60,
            capacity_provenance="PROVIDED",
            floor_level=3,
            floor_id="floor-3",
            block_id="block-a",
        )
        for index in (1, 2)
    ]
    replacements = [
        RoomInfo(
            id=f"replacement-{index}",
            code=f"A20{index}",
            resource_type="CLASSROOM",
            capacity=70,
            capacity_provenance="PROVIDED",
            floor_level=2,
            floor_id="floor-2",
            block_id="block-a",
        )
        for index in (1, 2)
    ]
    lab = RoomInfo(
        id="floor-3-lab",
        code="LAB-3",
        resource_type="LAB",
        capacity=40,
        capacity_provenance="PROVIDED",
        floor_level=3,
        floor_id="floor-3",
        lab_kind="CSE",
        block_id="block-a",
    )
    entries = [
        _entry(
            f"class-{index}",
            strength=60,
            section=f"section-{index}",
            faculty=f"faculty-{index}",
        )
        for index in (1, 2)
    ]
    for entry, room in zip(entries, classrooms):
        entry.base_room_id = room.id
    lab_entry = _entry("lab-class", strength=30, section="lab-section")
    lab_entry.required_room_type = "LAB"
    lab_entry.required_lab_kind = "CSE"
    lab_entry.base_room_id = lab.id
    rooms = classrooms + replacements + [lab]
    state = ScenarioState(
        entries=entries + [lab_entry],
        rooms=rooms,
        unavailable_rooms=set(),
        occupied_slots={},
        affected_entry_ids=set(),
        change_descriptions=[],
    )

    changed = apply_scenario_changes(state, [{
        "type": "ROOM_UNAVAILABLE",
        "payload": {"room_ids": [room.id for room in classrooms]},
    }])
    result = AllocationOptimizer(
        entries=[entry for entry in changed.entries if entry.id in changed.affected_entry_ids],
        rooms=changed.rooms,
        unavailable_rooms=changed.unavailable_rooms,
        occupied_slots=changed.occupied_slots,
        unavailable_room_slots=changed.unavailable_room_slots,
    ).solve()

    assert changed.affected_entry_ids == {entry.id for entry in entries}
    assert lab_entry.id not in changed.affected_entry_ids
    assert result.status == "FEASIBLE"
    assert set(result.assignments.values()) == {room.id for room in replacements}
    assigned = [next(room for room in rooms if room.id == room_id) for room_id in result.assignments.values()]
    assert all(
        room.capacity_provenance == "PROVIDED"
        and room.capacity >= entries[0].strength
        and room.resource_type == "CLASSROOM"
        for room in assigned
    )


def test_closing_rooms_across_floors_identifies_and_jointly_reallocates_all_classes():
    targets = [
        RoomInfo(
            id=f"target-{level}",
            code=f"A{level}01",
            resource_type="CLASSROOM",
            capacity=50,
            capacity_provenance="PROVIDED",
            floor_level=level,
            floor_id=f"floor-{level}",
            block_id="block-a",
        )
        for level in (1, 4)
    ]
    replacements = [
        RoomInfo(
            id=f"spare-{index}",
            code=f"SPARE-{index}",
            resource_type="CLASSROOM",
            capacity=65,
            capacity_provenance="PROVIDED",
            floor_level=level,
            floor_id=f"floor-{level}",
            block_id="block-a",
        )
        for index, level in enumerate((2, 5), start=1)
    ]
    entries = [
        _entry(
            f"cross-floor-class-{index}",
            strength=50,
            section=f"cross-floor-section-{index}",
            faculty=f"cross-floor-faculty-{index}",
        )
        for index in (1, 2)
    ]
    for entry, room in zip(entries, targets):
        entry.base_room_id = room.id
    state = ScenarioState(
        entries=entries,
        rooms=targets + replacements,
        unavailable_rooms=set(),
        occupied_slots={},
        affected_entry_ids=set(),
        change_descriptions=[],
    )

    changed = apply_scenario_changes(state, [{
        "type": "ROOM_UNAVAILABLE",
        "payload": {"room_ids": [room.id for room in targets]},
    }])
    result = AllocationOptimizer(
        entries=[entry for entry in changed.entries if entry.id in changed.affected_entry_ids],
        rooms=changed.rooms,
        unavailable_rooms=changed.unavailable_rooms,
        occupied_slots=changed.occupied_slots,
        unavailable_room_slots=changed.unavailable_room_slots,
    ).solve()

    assert changed.affected_entry_ids == {entry.id for entry in entries}
    assert result.status == "FEASIBLE"
    assert set(result.assignments.values()) == {room.id for room in replacements}
    for entry in entries:
        assigned_room = next(
            room for room in replacements if room.id == result.assignments[entry.id]
        )
        assert assigned_room.capacity is not None
        assert assigned_room.capacity >= entry.strength
        assert assigned_room.capacity_provenance == "PROVIDED"


@pytest.mark.parametrize(
    "room_code",
    ["B03", "B04", "B05", "SH-01", "SH-02", "AIML-LAB", "PHYS-LAB", "CHEM-LAB"],
)
def test_supplied_basement_room_closure_uses_inventory_capacity_and_facilities(room_code):
    rooms = _inventory_rooms("basement")
    target = next(room for room in rooms if room.code == room_code)
    is_lab = target.resource_type == "LAB"
    entry = _entry(
        f"class-{room_code}",
        strength=min(target.capacity or 1, 35) if is_lab else 40,
        facilities=target.facilities,
    )
    entry.required_room_type = target.resource_type
    entry.required_lab_kind = target.lab_kind
    entry.base_room_id = target.id
    state = ScenarioState(
        entries=[entry],
        rooms=rooms,
        unavailable_rooms=set(),
        occupied_slots={},
        affected_entry_ids=set(),
        change_descriptions=[],
    )

    changed = apply_scenario_changes(state, [{
        "type": "ROOM_UNAVAILABLE",
        "payload": {"room_ids": [target.id], "weekdays": [0]},
    }])
    result = AllocationOptimizer(
        entries=[entry],
        rooms=changed.rooms,
        unavailable_rooms=changed.unavailable_rooms,
        unavailable_room_slots=changed.unavailable_room_slots,
    ).solve()

    assert changed.affected_entry_ids == {entry.id}
    if is_lab:
        assert result.status == "PARTIAL"
        assert result.unresolved[0]["reason"] == "No compatible room available"
        assert result.unresolved[0]["near_miss_rooms"]
    else:
        assert result.status == "FEASIBLE"
        assigned = next(room for room in rooms if room.id == result.assignments[entry.id])
        assert assigned.capacity is not None and assigned.capacity >= entry.strength
        assert assigned.capacity_provenance == "PROVIDED"


def test_whole_basement_floor_closure_reports_all_classes_unresolved_without_capacity_data():
    rooms = _inventory_rooms("basement")
    entries = []
    for index, room in enumerate(rooms):
        entry = _entry(
            f"basement-class-{index}",
            weekday=index % 5,
            section=f"section-{index}",
            strength=40,
            facilities=room.facilities,
        )
        entry.required_room_type = room.resource_type
        entry.required_lab_kind = room.lab_kind
        entry.base_room_id = room.id
        entries.append(entry)
    state = ScenarioState(
        entries=entries,
        rooms=rooms,
        unavailable_rooms=set(),
        occupied_slots={},
        affected_entry_ids=set(),
        change_descriptions=[],
    )

    changed = apply_scenario_changes(state, [{
        "type": "FLOOR_UNAVAILABLE",
        "payload": {"floor_id": "floor_A_basement"},
    }])
    result = AllocationOptimizer(
        entries=[entry for entry in entries if entry.id in changed.affected_entry_ids],
        rooms=changed.rooms,
        unavailable_rooms=changed.unavailable_rooms,
        unavailable_room_slots=changed.unavailable_room_slots,
    ).solve()

    assert changed.affected_entry_ids == {entry.id for entry in entries}
    assert result.status == "PARTIAL"
    assert len(result.unresolved) == len(entries)


def test_timetable_occupied_replacement_room_is_rejected():
    rooms = _inventory_rooms("basement")
    b03 = next(room for room in rooms if room.code == "B03")
    b04 = next(room for room in rooms if room.code == "B04")
    entry = _entry("class-b03", strength=50, facilities=["PROJECTOR"])
    entry.base_room_id = b03.id
    state = ScenarioState(
        entries=[entry],
        rooms=[b03, b04],
        unavailable_rooms=set(),
        occupied_slots={(0, "P1"): {b04.id}},
        affected_entry_ids=set(),
        change_descriptions=[],
    )
    changed = apply_scenario_changes(state, [{
        "type": "ROOM_UNAVAILABLE",
        "payload": {"room_ids": [b03.id], "weekdays": [0]},
    }])

    result = AllocationOptimizer(
        entries=[entry],
        rooms=changed.rooms,
        occupied_slots=changed.occupied_slots,
        unavailable_room_slots=changed.unavailable_room_slots,
    ).solve()

    assert result.status == "PARTIAL"
    rejected = next(
        room for room in result.unresolved[0]["near_miss_rooms"]
        if room["room"] == "B04"
    )
    assert "occupied during 0-P1" in rejected["reasons"]


def test_estimated_capacity_is_not_presented_as_confirmed_or_allowed_when_too_small():
    rooms = _inventory_rooms("basement")
    lab = next(room for room in rooms if room.code == "AIML-LAB")
    entry = _entry("large-aiml-class", strength=36, facilities=lab.facilities)
    entry.required_room_type = "LAB"
    entry.required_lab_kind = "AIML"
    entry.base_room_id = None

    result = AllocationOptimizer([entry], [lab]).solve()

    assert result.status == "PARTIAL"
    candidate = result.unresolved[0]["near_miss_rooms"][0]
    assert candidate["capacity"] == 35
    assert candidate["capacity_provenance"] == "ESTIMATED"
    assert "capacity 35 < strength 36" in candidate["reasons"]


def test_recovery_does_not_calculate_capacity_gap_for_unknown_capacity():
    entry = _entry("unresolved", strength=30)
    state = ScenarioState(
        entries=[entry],
        rooms=[_room("unknown", capacity=None)],
        unavailable_rooms=set(),
        occupied_slots={},
        affected_entry_ids={entry.id},
        change_descriptions=[],
    )

    suggestions = _generate_recovery(
        [{"entry_id": entry.id}],
        state,
    )

    assert suggestions == [{
        "type": "TIME_SHIFT",
        "description": "Try shifting section-a's class to a different period where more rooms are available",
    }]
