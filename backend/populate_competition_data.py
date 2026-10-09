"""Populate directly supplied Block A records into the isolated demo database."""

from __future__ import annotations

import os
import re
import secrets
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

EXPECTED_DATABASE_URL = "sqlite:///./data/campus_demo.db"

if os.environ.get("DATABASE_URL") != EXPECTED_DATABASE_URL:
    raise SystemExit(
        f"Refusing population: DATABASE_URL must be exactly {EXPECTED_DATABASE_URL!r}."
    )

from app.db import Base, engine  # noqa: E402
from app.models.academic import Department, Section, Student  # noqa: E402
from app.models.campus import Block, Floor, Room  # noqa: E402
from app.models.identity import User  # noqa: E402
from app.models.navigation import NavNode  # noqa: E402
from app.security import get_password_hash  # noqa: E402


def _require_isolated_database() -> None:
    if make_url(str(engine.url)).database != "./data/campus_demo.db":
        raise SystemExit(f"Refusing population: unexpected engine URL {engine.url!s}.")

    target = (Path.cwd() / "data" / "campus_demo.db").resolve()
    expected = (Path(__file__).parent / "data" / "campus_demo.db").resolve()
    if Path.cwd().resolve() != Path(__file__).parent.resolve() or target != expected:
        raise SystemExit(
            "Refusing population: run this script from backend/ so the isolated "
            "database path resolves to backend/data/campus_demo.db."
        )


def _require_clean_current_schema() -> None:
    inspector = inspect(engine)
    expected_tables = set(Base.metadata.tables)
    actual_tables = set(inspector.get_table_names())
    if not expected_tables.issubset(actual_tables):
        missing = sorted(expected_tables - actual_tables)
        raise SystemExit(f"Refusing population: application tables missing: {missing}.")

    with engine.connect() as connection:
        nonempty = [
            table
            for table in sorted(actual_tables)
            if connection.execute(
                text(f'SELECT COUNT(*) FROM "{table}"')
            ).scalar_one()
        ]
    if nonempty:
        raise SystemExit(
            "Refusing population: expected a clean demo database; non-empty "
            f"tables found: {nonempty}."
        )


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _add_room(
    db: Session,
    *,
    floor_id: str,
    code: str,
    display_name: str,
    resource_type: str,
    department: str | None = None,
    capacity: int | None = None,
    lab_kind: str | None = None,
    facilities: list[str] | None = None,
    allocatable: bool = True,
    spare: bool = False,
    notes: str | None = None,
) -> Room:
    room_id = f"room_a_{_slug(code)}"
    room = Room(
        id=room_id,
        block_id="block_A",
        floor_id=floor_id,
        code=code,
        display_name=display_name,
        aliases=[],
        resource_type=resource_type,
        department=department,
        capacity=capacity,
        capacity_provenance="REAL" if capacity is not None else None,
        allocatable_for_classes=allocatable,
        reservable_for_events=False,
        lab_kind=lab_kind,
        facilities=facilities or [],
        accessible=None,
        status="ACTIVE",
        is_spare=spare,
        provenance="REAL",
        notes=notes,
    )
    db.add(room)
    db.flush()
    db.add(
        NavNode(
            id=f"nav_{room_id}",
            block_id="block_A",
            floor_id=floor_id,
            room_id=room_id,
            kind="ROOM",
        )
    )
    return room


def _populate(db: Session) -> None:
    block = Block(
        id="block_A",
        code="A",
        name="Block A",
        is_active=True,
        is_pilot=False,
    )
    db.add(block)

    floors = [
        ("floor_A_basement", -1, "Basement"),
        ("floor_A_ground", 0, "Ground Floor"),
        ("floor_A_1", 1, "1st Floor"),
        ("floor_A_2", 2, "2nd Floor"),
        ("floor_A_3", 3, "3rd Floor"),
        ("floor_A_4", 4, "4th Floor"),
        ("floor_A_5", 5, "5th Floor"),
    ]
    for floor_id, level, name in floors:
        db.add(
            Floor(
                id=floor_id,
                block_id=block.id,
                level=level,
                name=name,
                label=name,
            )
        )
    db.flush()

    rooms: dict[str, Room] = {}
    for code, capacity, purpose in (
        ("SH01", 90, "Seminar hall; intended for first-year CSE/seminar activities."),
        ("SH02", 75, "Seminar hall; intended for first-year CSE/seminar activities."),
    ):
        rooms[code] = _add_room(
            db,
            floor_id="floor_A_basement",
            code=code,
            display_name=f"Seminar Hall {code[-2:]}",
            resource_type="SEMINAR_HALL",
            capacity=capacity,
            notes=purpose,
        )

    for code, department, use in (
        ("B03", "AIML", "AI&ML first-year classroom."),
        ("B04", "ISE", "ISE first-year classroom."),
        ("B05", "DS", "Data Science first-year classroom."),
    ):
        rooms[code] = _add_room(
            db,
            floor_id="floor_A_basement",
            code=code,
            display_name=f"Classroom {code}",
            resource_type="CLASSROOM",
            department=department,
            notes=f"{use} Capacity not supplied; left unknown.",
        )

    basement_labs = [
        (
            "Shared Computer Lab",
            "SHARED-COMPUTER-LAB",
            "SHARED_COMPUTER",
            ["COMPUTERS"],
            "Shared by AIML, CSE, Data Science, and ISE. "
            "Owner-reported lab strength range is 35-40; exact room capacity is unknown.",
        ),
        (
            "Physics Lab",
            "PHYSICS-LAB",
            "PHYSICS",
            [],
            "Owner-reported lab strength range is 35-40; exact room capacity is unknown.",
        ),
        (
            "Chemistry Lab",
            "CHEMISTRY-LAB",
            "CHEMISTRY",
            [],
            "Owner-reported lab strength range is 35-40; exact room capacity is unknown.",
        ),
    ]
    for name, code, lab_kind, facilities, notes in basement_labs:
        rooms[code] = _add_room(
            db,
            floor_id="floor_A_basement",
            code=code,
            display_name=name,
            resource_type="LAB",
            lab_kind=lab_kind,
            facilities=facilities,
            notes=notes,
        )

    for name, resource_type in (
        ("Principal Room", "OFFICE"),
        ("Enquiry Room", "OFFICE"),
        ("Meeting Hall", "MEETING_HALL"),
        ("HOD Room", "OFFICE"),
        ("Admission Section", "OFFICE"),
    ):
        rooms[name] = _add_room(
            db,
            floor_id="floor_A_ground",
            code=name,
            display_name=name,
            resource_type=resource_type,
            allocatable=False,
        )

    unknown_classroom_capacity_note = (
        "Exact capacity not supplied; capacity left unknown."
    )
    for number in range(101, 109):
        code = f"A{number}"
        rooms[code] = _add_room(
            db,
            floor_id="floor_A_1",
            code=code,
            display_name=f"Classroom {code}",
            resource_type="CLASSROOM",
            department="CSE",
            notes=(
                "Owner-provided capacity range is 60-75. "
                + unknown_classroom_capacity_note
            ),
        )
    rooms["A109"] = _add_room(
        db,
        floor_id="floor_A_1",
        code="A109",
        display_name="Empty Classroom A109",
        resource_type="CLASSROOM",
        department="CSE",
        spare=True,
        notes=unknown_classroom_capacity_note,
    )
    for index in (1, 2):
        code = f"CSE-LAB-{index}"
        rooms[code] = _add_room(
            db,
            floor_id="floor_A_1",
            code=code,
            display_name=f"CSE Lab {index}",
            resource_type="LAB",
            department="CSE",
            lab_kind="CSE",
            notes="Owner provided two CSE labs; sequence is a local label.",
        )

    for number in range(201, 209):
        code = f"A{number}"
        rooms[code] = _add_room(
            db,
            floor_id="floor_A_2",
            code=code,
            display_name=f"Classroom {code}",
            resource_type="CLASSROOM",
            department="ISE",
            notes=(
                "Owner-provided capacity range is 60-75. "
                + unknown_classroom_capacity_note
            ),
        )
    rooms["A209"] = _add_room(
        db,
        floor_id="floor_A_2",
        code="A209",
        display_name="Empty Classroom A209",
        resource_type="CLASSROOM",
        department="ISE",
        spare=True,
        notes=unknown_classroom_capacity_note,
    )
    for index in (1, 2):
        code = f"ISE-LAB-{index}"
        rooms[code] = _add_room(
            db,
            floor_id="floor_A_2",
            code=code,
            display_name=f"ISE Lab {index}",
            resource_type="LAB",
            department="ISE",
            lab_kind="ISE",
            notes="Owner provided two ISE labs; sequence is a local label.",
        )

    department_rooms = [
        ("A301", "Civil 2", "CIVIL"),
        ("A302", "Mech 2", "MECH"),
        ("A303", "Civil 3", "CIVIL"),
        ("A304", "Mech 3", "MECH"),
        ("A305", "Cyber 2", "CYBER"),
        ("A306", "Cyber 3", "CYBER"),
    ]
    for code, use, department in department_rooms:
        rooms[code] = _add_room(
            db,
            floor_id="floor_A_3",
            code=code,
            display_name=f"Classroom {code}",
            resource_type="CLASSROOM",
            department=department,
            notes=f"Owner-provided use: {use}. Capacity not supplied.",
        )
    for index in (1, 2):
        code = f"CIVIL-MECH-LAB-{index}"
        rooms[code] = _add_room(
            db,
            floor_id="floor_A_3",
            code=code,
            display_name=f"Civil/Mech Lab {index}",
            resource_type="LAB",
            lab_kind="CIVIL_MECH",
            notes="Owner provided two Civil/Mech labs; sequence is a local label.",
        )

    ds_rooms = [
        ("A401", "DS 2A"),
        ("A402", "DS 2B"),
        ("A403", "DS 3A"),
        ("A404", "DS 3B"),
        ("A405", "DS 4A"),
        ("A406", "DS 4B"),
    ]
    for code, use in ds_rooms:
        rooms[code] = _add_room(
            db,
            floor_id="floor_A_4",
            code=code,
            display_name=f"Classroom {code}",
            resource_type="CLASSROOM",
            department="DS",
            notes=f"Owner-provided use: {use}. Capacity not supplied.",
        )
    for code in ("A407", "A408"):
        rooms[code] = _add_room(
            db,
            floor_id="floor_A_4",
            code=code,
            display_name=f"Empty Classroom {code}",
            resource_type="CLASSROOM",
            department="DS",
            spare=True,
            notes=unknown_classroom_capacity_note,
        )
    for index in (1, 2):
        code = f"DS-LAB-{index}"
        rooms[code] = _add_room(
            db,
            floor_id="floor_A_4",
            code=code,
            display_name=f"Data Science Lab {index}",
            resource_type="LAB",
            department="DS",
            lab_kind="DATA_SCIENCE",
            notes="Owner provided two Data Science labs; sequence is a local label.",
        )

    aiml_sections = {
        "A501": "AIML 2A",
        "A502": "AIML 3A",
        "A503": "AIML 4A",
    }
    for code, use in aiml_sections.items():
        rooms[code] = _add_room(
            db,
            floor_id="floor_A_5",
            code=code,
            display_name=f"Classroom {code}",
            resource_type="CLASSROOM",
            department="AIML",
            notes=f"Owner-provided use: {use}. Capacity not supplied.",
        )
    for code in ("A504", "A505"):
        rooms[code] = _add_room(
            db,
            floor_id="floor_A_5",
            code=code,
            display_name=f"AI&ML Lab-Oriented Personal-Use Room {code}",
            resource_type="SPECIAL_USE",
            department="AIML",
            allocatable=False,
            notes=(
                "Owner-described lab-oriented classroom/personal-use room if "
                "labs are unavailable; not modeled as an ordinary classroom."
            ),
        )
    for code in ("A506", "A507", "A508"):
        rooms[code] = _add_room(
            db,
            floor_id="floor_A_5",
            code=code,
            display_name=f"Empty Classroom {code}",
            resource_type="CLASSROOM",
            department="AIML",
            spare=True,
            notes=unknown_classroom_capacity_note,
        )

    department_names = (
        "CSE",
        "ISE",
        "CIVIL",
        "MECH",
        "CYBER",
        "DS",
        "AIML",
        "FIRST_YEAR",
    )
    departments: dict[str, Department] = {}
    for name in department_names:
        department = Department(id=f"dept_{name.casefold()}", name=name)
        db.add(department)
        departments[name] = department
    db.flush()

    sections_data: list[tuple[str, int, str, int, str | None]] = []
    sections_data += [
        ("CSE", 2, "A", 65, None),
        ("CSE", 2, "B", 60, None),
        ("CSE", 3, "A", 64, None),
        ("CSE", 3, "B", 58, None),
        ("CSE", 4, "A", 50, None),
        ("CSE", 4, "B", 55, None),
    ]
    sections_data += [
        ("ISE", 2, "A", 50, None),
        ("ISE", 2, "B", 50, None),
        ("ISE", 2, "C", 60, None),
        ("ISE", 3, "A", 58, None),
        ("ISE", 3, "B", 55, None),
        ("ISE", 4, "A", 60, None),
        ("ISE", 4, "B", 58, None),
        ("ISE", 4, "C", 58, None),
    ]
    sections_data += [
        ("CIVIL", 2, "", 30, "A301"),
        ("MECH", 2, "", 35, "A302"),
        ("CIVIL", 3, "", 40, "A303"),
        ("MECH", 3, "", 40, "A304"),
        ("CYBER", 2, "", 60, "A305"),
        ("CYBER", 3, "", 64, "A306"),
    ]
    sections_data += [
        ("DS", 2, "A", 64, "A401"),
        ("DS", 2, "B", 60, "A402"),
        ("DS", 3, "A", 68, "A403"),
        ("DS", 3, "B", 62, "A404"),
        ("DS", 4, "A", 60, "A405"),
        ("DS", 4, "B", 58, "A406"),
    ]
    sections_data += [
        ("AIML", 2, "A", 58, "A501"),
        ("AIML", 3, "A", 60, "A502"),
        ("AIML", 4, "A", 54, "A503"),
    ]

    section_ids: dict[tuple[str, int, str], str] = {}
    for department, year, suffix, strength, home_room_code in sections_data:
        code = f"{department} {year}{suffix}".strip()
        section_id = f"sec_{_slug(code)}"
        section_ids[(department, year, suffix)] = section_id
        db.add(
            Section(
                id=section_id,
                department_id=departments[department].id,
                code=code,
                name=code,
                year=year,
                strength=strength,
                strength_provenance="REAL",
                home_room_id=rooms[home_room_code].id if home_room_code else None,
                is_synthetic=False,
                provenance="REAL",
            )
        )
    db.flush()

    cse_3a_id = section_ids[("CSE", 3, "A")]
    named_students = (
        "Shailendra Kumar",
        "Shreyas",
        "Sulaksha",
        "Sneha",
        "Srivanth",
        "Harsha",
        "Shrikanth",
    )
    pending_students: list[Student] = []
    for index, name in enumerate(named_students, 1):
        student_id = f"student_cse3a_real_{index:02d}"
        user_id = f"user_{student_id}"
        db.add(
            User(
                id=user_id,
                email=f"cse3a-owner-provided-{index:02d}@example.invalid",
                hashed_password=get_password_hash(secrets.token_urlsafe(32)),
                role="STUDENT",
                display_name=name,
                active=False,
            )
        )
        pending_students.append(
            Student(
                id=student_id,
                user_id=user_id,
                section_id=cse_3a_id,
                profile={
                    "provenance": "REAL",
                    "email_provenance": "SYNTHETIC_PLACEHOLDER",
                    "note": "Only the owner-provided name is populated.",
                },
                anon_code=None,
            )
        )

    for index in range(1, 58):
        student_id = f"student_cse3a_synthetic_{index:03d}"
        user_id = f"user_{student_id}"
        db.add(
            User(
                id=user_id,
                email=f"cse3a-synthetic-{index:03d}@example.invalid",
                hashed_password=get_password_hash(secrets.token_urlsafe(32)),
                role="STUDENT",
                display_name=f"Synthetic Student CSE 3A-{index:03d}",
                active=False,
            )
        )
        pending_students.append(
            Student(
                id=student_id,
                user_id=user_id,
                section_id=cse_3a_id,
                anon_code=f"CSE3A-SYN-{index:03d}",
                profile={
                    "provenance": "SYNTHETIC",
                    "note": "Generated only to represent the owner-provided remaining section count.",
                },
            )
        )

    db.flush()
    db.add_all(pending_students)
    db.flush()


def main() -> None:
    _require_isolated_database()
    _require_clean_current_schema()

    with Session(engine) as db, db.begin():
        _populate(db)

    print(
        "Population committed to backend/data/campus_demo.db: "
        "1 block, 7 floors, 61 locations, 8 departments, 29 sections, "
        "64 CSE 3A student identities (7 REAL names, 57 SYNTHETIC)."
    )
    print(
        "No faculty, subjects, timetable entries, food records, attendance, "
        "marks, academic history, emergency contacts, or route edges were created."
    )


if __name__ == "__main__":
    main()
