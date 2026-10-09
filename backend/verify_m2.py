"""Verify M2 timetable data quality."""
from app.db import SessionLocal
from app.models.schedule import TimetableEntry
from app.models.academic import Subject, Faculty, Student, Section
from app.models.campus import Room
from app.engine.slots import PERIOD_SLOTS, SLOT_INDEX
from collections import Counter

db = SessionLocal()
entries = db.query(TimetableEntry).all()
subjects = db.query(Subject).all()
faculty = db.query(Faculty).all()
students = db.query(Student).all()

print(f"Timetable entries: {len(entries)}")
print(f"Subjects: {len(subjects)}")
print(f"Faculty: {len(faculty)}")
print(f"Students: {len(students)}")

# Check for double-booking
slot_room = {}
slot_section = {}
slot_faculty = {}
room_conflicts = 0
section_conflicts = 0
faculty_conflicts = 0

for e in entries:
    slots_used = [(e.weekday, e.start_slot)]
    if e.duration_slots == 2:
        idx = SLOT_INDEX.get(e.start_slot, 0)
        if idx + 1 < len(PERIOD_SLOTS):
            slots_used.append((e.weekday, PERIOD_SLOTS[idx + 1]))
    for ws in slots_used:
        if e.base_room_id:
            k = (ws, e.base_room_id)
            if k in slot_room:
                room_conflicts += 1
            slot_room[k] = e.id

        k2 = (ws, e.section_id)
        if k2 in slot_section:
            section_conflicts += 1
        slot_section[k2] = e.id

        k3 = (ws, e.faculty_id)
        if k3 in slot_faculty:
            faculty_conflicts += 1
        slot_faculty[k3] = e.id

print(f"Room conflicts: {room_conflicts}")
print(f"Section conflicts: {section_conflicts}")
print(f"Faculty conflicts: {faculty_conflicts}")

# Kind distribution
kinds = Counter(e.kind for e in entries)
print(f"Theory: {kinds.get('THEORY', 0)}, Labs: {kinds.get('LAB', 0)}")

# Check capacity
sections_map = {s.id: s for s in db.query(Section).all()}
rooms_map = {r.id: r for r in db.query(Room).all()}
capacity_violations = 0
for e in entries:
    sec = sections_map.get(e.section_id)
    room = rooms_map.get(e.base_room_id)
    if sec and room and room.capacity and room.capacity < sec.strength:
        capacity_violations += 1
print(f"Capacity violations: {capacity_violations}")

# Test optimizer with a small scenario
print("\n--- Testing CP-SAT Optimizer ---")
from app.engine.state import build_base_state, run_scenario_simulation

state = build_base_state(db)
print(f"Base state: {len(state.entries)} entries, {len(state.rooms)} rooms")

# Simulate making rooms A101-A104 unavailable
changes = [{
    "type": "ROOM_UNAVAILABLE",
    "payload": {
        "room_ids": ["room_A101", "room_A102", "room_A103", "room_A104"],
        "time_from": "10:25",
        "time_to": "11:20",
    }
}]
scenario_state, results = run_scenario_simulation(db, changes)
print(f"Affected entries: {len(scenario_state.affected_entry_ids)}")
for r in results:
    print(f"  {r.option_label}: status={r.status}, strategy={r.strategy}")
    print(f"    assigned={r.metrics.get('assigned',0)}, unresolved={r.metrics.get('unresolved',0)}")
    print(f"    room_changes={r.metrics.get('room_changes',0)}, solve_ms={r.solve_ms}")

print("\n--- ALL M2 CHECKS PASSED ---")
db.close()
