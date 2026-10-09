"""Add explicitly sourced and configured timetable data to campus_demo.db."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

EXPECTED_DATABASE_URL = "sqlite:///./data/campus_demo.db"
PDF_PATH = Path(__file__).resolve().parent.parent / "data" / "FFINAL-5th  SEM CSE TT.pdf"

if os.environ.get("DATABASE_URL") != EXPECTED_DATABASE_URL:
    raise SystemExit(f"DATABASE_URL must be exactly {EXPECTED_DATABASE_URL!r}.")

from app.db import engine  # noqa: E402
from app.models.academic import Department, Faculty, Section, Student, Subject  # noqa: E402
from app.models.campus import Block, Room  # noqa: E402
from app.models.identity import Setting, User  # noqa: E402
from app.models.schedule import TimetableEntry  # noqa: E402
from app.security import get_password_hash  # noqa: E402


def require_target_database() -> None:
    if make_url(str(engine.url)).database != "./data/campus_demo.db":
        raise SystemExit(f"Refusing non-target database URL: {engine.url!s}")
    backend = Path(__file__).resolve().parent
    if Path.cwd().resolve() != backend:
        raise SystemExit("Run this script with backend/ as the working directory.")
    if not PDF_PATH.is_file():
        raise SystemExit(f"Supplied timetable PDF is missing: {PDF_PATH}")


def require_expected_state(db: Session) -> None:
    expected_counts = {
        Block.__tablename__: 1,
        "floors": 7,
        Room.__tablename__: 61,
        Department.__tablename__: 8,
        Section.__tablename__: 29,
        Student.__tablename__: 64,
        Faculty.__tablename__: 0,
        Subject.__tablename__: 0,
        TimetableEntry.__tablename__: 0,
    }
    for table, expected in expected_counts.items():
        actual = db.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar_one()
        if actual != expected:
            raise SystemExit(
                f"Refusing to continue: expected {expected} rows in {table}, found {actual}."
            )
    keys = (
        "competition_timetable_review",
        "competition_synthetic_schedule_unresolved",
        "competition_teaching_relationships",
    )
    present = db.query(Setting.key).filter(Setting.key.in_(keys)).all()
    if present:
        raise SystemExit(
            "Refusing to duplicate prior timetable continuation data: "
            + ", ".join(row[0] for row in present)
        )


PDF_FACULTY = {
    "sd": ("Faculty PDF-SD", "Sanjay Das"),
    "sa": ("Faculty PDF-SA", "Swathi A"),
    "ks": ("Faculty PDF-KS", "Keerthana Shankar"),
    "shk": ("Faculty PDF-SHK", "Sushanth Kumar"),
    "ss": ("Faculty PDF-SS", "Shalini S"),
    "al": ("Faculty PDF-AL", "Asha Latha"),
    "ukc": ("Faculty PDF-UKC", "Usha K C"),
    "mn": ("Faculty PDF-MN", "Meghana Nigam"),
    "sk": ("Faculty PDF-SK", "Shivanna K"),
    "db": ("Faculty PDF-DB", "Dasari Bhulakshmi"),
}

NAMED_FACULTY = {
    "swetha": ("Swetha", "REAL"),
    "parvathish": ("Parvathish", "REAL"),
}

SYNTHETIC_FACULTY = {
    "cse": "Faculty CSE-01",
    "ise": "Faculty ISE-01",
    "engineering": "Faculty Engineering-01",
}


def create_faculty(db: Session) -> dict[str, Faculty]:
    result: dict[str, Faculty] = {}
    all_faculty = {
        **{key: (name, "REAL_TIMETABLE_PDF") for key, (_, name) in PDF_FACULTY.items()},
        **NAMED_FACULTY,
        **{key: (name, "SYNTHETIC") for key, name in SYNTHETIC_FACULTY.items()},
    }
    for key, (name, provenance) in all_faculty.items():
        faculty_id = f"faculty_{key}"
        user_id = f"user_{faculty_id}"
        user = User(
            id=user_id,
            email=f"{faculty_id}@example.invalid",
            hashed_password=get_password_hash(os.urandom(32).hex()),
            role="FACULTY",
            display_name=name,
            active=False,
        )
        db.add(user)
        db.flush()
        faculty = Faculty(
            id=faculty_id,
            user_id=user_id,
            department_id="dept_cse" if key in PDF_FACULTY or key in {"swetha", "parvathish", "cse"} else None,
            name=name,
            employee_id=None,
            designation=None,
            is_synthetic=provenance == "SYNTHETIC",
        )
        db.add(faculty)
        result[key] = faculty
    db.flush()
    return result


SUBJECTS: dict[str, dict[str, Any]] = {}
CURRICULA_TEMPLATES: dict[tuple[str, int], dict[str, Any]] = {}


def add_subject(
    key: str,
    code: str,
    name: str,
    *,
    department_id: str | None,
    provenance: str,
    kind: str = "THEORY",
    lab_kind: str | None = None,
) -> None:
    SUBJECTS[key] = {
        "id": f"subject_{key}",
        "code": code,
        "name": name,
        "department_id": department_id,
        "provenance": provenance,
        "kind": kind,
        "lab_kind": lab_kind,
    }


def create_subjects(db: Session) -> dict[str, Subject]:
    cse = "dept_cse"
    ise = "dept_ise"
    civil = "dept_civil"
    mech = "dept_mech"
    cyber = "dept_cyber"
    ds = "dept_ds"
    aiml = "dept_aiml"

    real = "REAL"
    pdf = "REAL_TIMETABLE_PDF"
    synthetic = "SYNTHETIC"

    add_subject("edc", "EDC", "Electronic Devices and Circuits", department_id=cse, provenance=real)
    add_subject("dbms", "DBMS", "Database Management Systems", department_id=cse, provenance=real)
    add_subject("python", "PYTHON", "Python", department_id=cse, provenance=real)
    add_subject("daa", "DAA", "Design and Analysis of Algorithms", department_id=cse, provenance=real)
    add_subject("ml", "ML", "Machine Learning", department_id=cse, provenance="REAL+REAL_TIMETABLE_PDF")

    for key, code, name, kind, lab_kind in (
        ("fcg", "BCS501", "Fundamentals of Computer Graphics", "THEORY", None),
        ("toc", "BCS503", "Theory of Computation and Compiler Design", "THEORY", None),
        ("nexgen", "BCSL504", "Next Generation Embedded Lab", "LAB", "NEX_GEN"),
        ("pecns", "BCS515B", "PE - Cryptography and Network Security", "THEORY", None),
        ("mad", "BCS506", "Mobile Application Development", "THEORY", None),
        ("rm", "BRM507A", "Research Methodology and IPR", "THEORY", None),
        ("evs", "B**K507", "Environmental Studies and E-waste Management", "THEORY", None),
    ):
        add_subject(key, code, name, department_id=cse, provenance=pdf, kind=kind, lab_kind=lab_kind)

    def template(
        dept: str,
        year: int,
        theory: list[tuple[str, str, str]],
        labs: list[tuple[str, str, str]] | None = None,
    ) -> None:
        course_keys: list[str] = []
        theory_keys: list[str] = []
        lab_keys: list[str] = []
        for code, name, key in theory:
            if key not in SUBJECTS:
                add_subject(
                    key,
                    code,
                    name,
                    department_id=dept,
                    provenance=synthetic,
                )
            course_keys.append(key)
            theory_keys.append(key)
        for code, name, key in labs or []:
            if key not in SUBJECTS:
                add_subject(
                    key,
                    code,
                    name,
                    department_id=dept,
                    provenance=synthetic,
                    kind="LAB",
                    lab_kind=key.upper(),
                )
            course_keys.append(key)
            lab_keys.append(key)
        CURRICULA_TEMPLATES[(dept, year)] = {
            "subjects": course_keys,
            "theory": theory_keys[:5],
            "labs": lab_keys,
        }

    template(
        cse,
        1,
        [
            ("CSE1-MATH", "Engineering Mathematics I", "cse1_math"),
            ("CSE1-PHY", "Engineering Physics", "cse1_physics"),
            ("CSE1-CHEM", "Engineering Chemistry", "cse1_chemistry"),
            ("PYTHON", "Python", "python"),
            ("CSE1-ENG", "English and Communication", "cse1_english"),
            ("CSE1-ELEC", "Basic Electrical and Electronics", "cse1_electronics"),
            ("CSE1-GRAPH", "Engineering Graphics", "cse1_graphics"),
        ],
        [("CSE1-PROG-LAB", "Programming Laboratory", "cse1_programming_lab")],
    )
    template(
        cse,
        2,
        [
            ("CSE2-DSA", "Data Structures and Algorithms", "cse2_dsa"),
            ("DAA", "Design and Analysis of Algorithms", "daa"),
            ("DBMS", "Database Management Systems", "dbms"),
            ("EDC", "Electronic Devices and Circuits", "edc"),
            ("CSE2-MATH", "Engineering Mathematics II", "cse2_math"),
            ("CSE2-OOP", "Object-Oriented Programming", "cse2_oop"),
            ("CSE2-CO", "Computer Organization", "cse2_co"),
        ],
        [("CSE2-LAB", "CSE Programming Laboratory", "cse2_lab")],
    )
    CURRICULA_TEMPLATES[(cse, 3)] = {
        "subjects": ["fcg", "ml", "toc", "nexgen", "pecns", "mad", "rm", "evs"],
        "theory": ["fcg", "ml", "toc", "pecns", "mad"],
        "labs": ["nexgen"],
    }
    template(
        cse,
        4,
        [
            ("CSE4-AI", "Artificial Intelligence", "cse4_ai"),
            ("CSE4-CLOUD", "Cloud Computing", "cse4_cloud"),
            ("CSE4-SEC", "Cybersecurity", "cse4_security"),
            ("CSE4-ELECT", "Technical Elective", "cse4_elective"),
            ("CSE4-PROJ", "Final-Year Project", "cse4_project"),
            ("CSE4-PROF", "Professional Practice and Management", "cse4_professional"),
        ],
        [("CSE4-PROJ-LAB", "Project Laboratory", "cse4_project_lab")],
    )

    template(ise, 2, [
        ("ISE2-DSA", "Data Structures and Algorithms", "ise2_dsa"),
        ("ISE2-DBMS", "Database Management Systems", "ise2_dbms"),
        ("ISE2-OOP", "Object-Oriented Programming", "ise2_oop"),
        ("ISE2-MATH", "Engineering Mathematics II", "ise2_math"),
        ("ISE2-OS", "Operating Systems", "ise2_os"),
    ], [("ISE2-LAB", "ISE Programming Laboratory", "ise2_lab")])
    template(ise, 3, [
        ("ISE3-CN", "Computer Networks", "ise3_cn"),
        ("ISE3-SE", "Software Engineering", "ise3_se"),
        ("ISE3-AI", "Applied Artificial Intelligence", "ise3_ai"),
        ("ISE3-CLOUD", "Cloud Computing", "ise3_cloud"),
        ("ISE3-SEC", "Information Security", "ise3_security"),
    ], [("ISE3-LAB", "ISE Systems Laboratory", "ise3_lab")])
    template(ise, 4, [
        ("ISE4-CLOUD", "Advanced Cloud Computing", "ise4_cloud"),
        ("ISE4-SEC", "Cybersecurity", "ise4_security"),
        ("ISE4-AI", "Applied Artificial Intelligence", "ise4_ai"),
        ("ISE4-ELECT", "Technical Elective", "ise4_elective"),
        ("ISE4-PROJ", "Final-Year Project", "ise4_project"),
    ], [("ISE4-PROJ-LAB", "Project Laboratory", "ise4_project_lab")])

    for dept, short, display in (
        (ds, "DS", "Data Science"),
        (aiml, "AIML", "AI and Machine Learning"),
        (cyber, "CYBER", "Cybersecurity"),
    ):
        for year in (2, 3, 4):
            template(
                dept,
                year,
                [
                    (f"{short}{year}-MATH", f"{display} Mathematics", f"{short.lower()}{year}_math"),
                    (f"{short}{year}-DATA", f"{display} Data Engineering", f"{short.lower()}{year}_data"),
                    (f"{short}{year}-AI", f"{display} Applied AI", f"{short.lower()}{year}_ai"),
                    (f"{short}{year}-SYS", f"{display} Systems", f"{short.lower()}{year}_systems"),
                    (f"{short}{year}-ELECT", "Technical Elective", f"{short.lower()}{year}_elective"),
                ],
                [(f"{short}{year}-LAB", f"{display} Laboratory", f"{short.lower()}{year}_lab")],
            )

    for dept, short, display in ((civil, "CIVIL", "Civil Engineering"), (mech, "MECH", "Mechanical Engineering")):
        for year in (2, 3):
            template(
                dept,
                year,
                [
                    (f"{short}{year}-MATH", f"{display} Mathematics", f"{short.lower()}{year}_math"),
                    (f"{short}{year}-CORE1", f"{display} Core Engineering I", f"{short.lower()}{year}_core1"),
                    (f"{short}{year}-CORE2", f"{display} Core Engineering II", f"{short.lower()}{year}_core2"),
                    (f"{short}{year}-DESIGN", f"{display} Design", f"{short.lower()}{year}_design"),
                    (f"{short}{year}-ELECT", "Technical Elective", f"{short.lower()}{year}_elective"),
                ],
                [(f"{short}{year}-LAB", f"{display} Laboratory", f"{short.lower()}{year}_lab")],
            )

    result: dict[str, Subject] = {}
    for key, data in SUBJECTS.items():
        provenance = data["provenance"]
        if provenance == "REAL":
            description = "Owner-provided subject. Provenance: REAL."
        elif provenance == "REAL_TIMETABLE_PDF":
            description = "Extracted from the supplied fifth-semester CSE timetable PDF."
        elif provenance == "REAL+REAL_TIMETABLE_PDF":
            description = (
                "Owner-provided subject and appears in the supplied fifth-semester "
                "CSE timetable PDF."
            )
        else:
            description = (
                "Configured synthetic curriculum for demonstration only; not a "
                "verified DSATM syllabus."
            )
        subject = Subject(
            id=data["id"],
            code=data["code"],
            name=data["name"],
            description=description,
            department_id=data["department_id"],
            kind=data["kind"],
            required_facilities=[],
            lab_kind=data["lab_kind"],
            is_synthetic=provenance == "SYNTHETIC",
        )
        db.add(subject)
        result[key] = subject
    db.flush()
    return result


def create_first_year_sections(db: Session) -> dict[str, Section]:
    result: dict[str, Section] = {}
    for suffix in ("A", "B"):
        code = f"CSE 1{suffix}"
        section_id = f"sec_cse-1{suffix.lower()}"
        section = Section(
            id=section_id,
            department_id="dept_cse",
            code=code,
            name=code,
            year=1,
            strength=60,
            strength_provenance="SYNTHETIC",
            home_room_id=None,
            is_synthetic=True,
            provenance="SYNTHETIC",
        )
        db.add(section)
        result[code] = section
    db.flush()
    return result


PDF_ROWS = [
    ("5A", "MON", "P1", "fcg", "sd"),
    ("5A", "MON", "P2", "toc", "sa"),
    ("5A", "MON", "P3", "pecns", "ks"),
    ("5A", "MON", "P7", "ml", "shk"),
    ("5A", "TUE", "P1", "fcg", "sd"),
    ("5A", "TUE", "P2", "fcg", "sd"),
    ("5A", "TUE", "P3", "toc", "sa"),
    ("5A", "TUE", "P4", "pecns", "ks"),
    ("5A", "TUE", "P5", "rm", "ss"),
    ("5A", "TUE", "P6", "pecns", "ks"),
    ("5A", "WED", "P3", "toc", "sa"),
    ("5A", "WED", "P4", "ml", "shk"),
    ("5A", "FRI", "P3", "pecns", "ks"),
    ("5A", "FRI", "P4", "ml", "shk"),
    ("5A", "FRI", "P5", "ml", "shk"),
    ("5A", "FRI", "P6", "fcg", "sd"),
    ("5A", "FRI", "P7", "toc", "sa"),
    ("5B", "MON", "P1", "pecns", "al"),
    ("5B", "MON", "P2", "ml", "ukc"),
    ("5B", "MON", "P5", "rm", "db"),
    ("5B", "MON", "P6", "ml", "ukc"),
    ("5B", "MON", "P7", "toc", "sk"),
    ("5B", "TUE", "P1", "ml", "ukc"),
    ("5B", "TUE", "P2", "pecns", "al"),
    ("5B", "TUE", "P3", "fcg", "mn"),
    ("5B", "TUE", "P6", "toc", "sk"),
    ("5B", "TUE", "P7", "fcg", "mn"),
    ("5B", "WED", "P1", "ml", "ukc"),
    ("5B", "WED", "P2", "fcg", "mn"),
    ("5B", "WED", "P3", "toc", "sk"),
    ("5B", "WED", "P6", "pecns", "al"),
    ("5B", "THU", "P1", "toc", "sk"),
    ("5B", "THU", "P2", "fcg", "mn"),
    ("5B", "THU", "P3", "pecns", "al"),
]


def import_pdf_rows(
    db: Session,
    faculty: dict[str, Faculty],
    subjects: dict[str, Subject],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sections = {
        "5A": db.query(Section).filter(Section.code == "CSE 3A").one(),
        "5B": db.query(Section).filter(Section.code == "CSE 3B").one(),
    }
    days = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4}
    room_sources = {"5A": "202", "5B": "203"}
    room_conflicts: list[dict[str, Any]] = []
    for section_label, day, slot, subject_key, faculty_key in PDF_ROWS:
        row_id = f"pdf_{section_label.lower()}_{day.lower()}_{slot.lower()}_{subject_key}"
        db.add(
            TimetableEntry(
                id=row_id,
                section_id=sections[section_label].id,
                subject_id=subjects[subject_key].id,
                faculty_id=faculty[faculty_key].id,
                weekday=days[day],
                start_slot=slot,
                duration_slots=1,
                kind="THEORY",
                required_room_type="CLASSROOM",
                required_lab_kind=None,
                required_facilities=[],
                base_room_id=None,
                provenance="REAL_TIMETABLE_PDF",
            )
        )
        room_conflicts.append(
            {
                "entry_id": row_id,
                "source_section": section_label,
                "target_section": sections[section_label].code,
                "day": day,
                "slot": slot,
                "source_room": room_sources[section_label],
                "status": "NEEDS_REVIEW",
                "reason": (
                    f"PDF classroom {room_sources[section_label]} does not map to "
                    "the owner-specified CSE classroom master data. No room assigned."
                ),
            }
        )

    unmapped_rows: list[dict[str, Any]] = [
        {
            "source_section": "5A",
            "target_section": "CSE 3A",
            "day": "WED",
            "source_row": "CG LAB / NEXT GEN LAB; B1/B2 instructor splits",
            "status": "NEEDS_REVIEW",
            "reason": "Lab groups/period span and room mapping cannot be resolved safely.",
        },
        {
            "source_section": "5A",
            "target_section": "CSE 3A",
            "day": "FRI",
            "source_row": "CG LAB / NEXT GEN LAB; B1/B2 instructor splits",
            "status": "NEEDS_REVIEW",
            "reason": "Lab groups/period span and room mapping cannot be resolved safely.",
        },
        {
            "source_section": "5A",
            "target_section": "CSE 3A",
            "day": "MON",
            "source_row": "ML LAB; initials SK, RKP, RS",
            "status": "NEEDS_REVIEW",
            "reason": "The lab room and the listed multi-faculty/group allocation are ambiguous.",
        },
        {
            "source_section": "5A",
            "target_section": "CSE 3A",
            "day": "WED/THU",
            "source_row": "NPTEL / MOOC blocks",
            "status": "NEEDS_REVIEW",
            "reason": "Source cells merge across periods and do not identify a single subject/faculty assignment.",
        },
        {
            "source_section": "5A",
            "target_section": "CSE 3A",
            "day": "FRI",
            "source_row": "EVS",
            "status": "NEEDS_REVIEW",
            "reason": "The subject appears in the weekly grid but its faculty initials are not unambiguous.",
        },
        {
            "source_section": "5B",
            "target_section": "CSE 3B",
            "day": "MON",
            "source_row": "CG LAB / NEXT GEN LAB; B1/B2 instructor splits",
            "status": "NEEDS_REVIEW",
            "reason": "Lab groups/period span and room mapping cannot be resolved safely.",
        },
        {
            "source_section": "5B",
            "target_section": "CSE 3B",
            "day": "TUE",
            "source_row": "CG LAB / NEXT GEN LAB; B1/B2 instructor splits",
            "status": "NEEDS_REVIEW",
            "reason": "Lab groups/period span and room mapping cannot be resolved safely.",
        },
        {
            "source_section": "5B",
            "target_section": "CSE 3B",
            "day": "WED",
            "source_row": "ML LAB; multiple faculty initials",
            "status": "NEEDS_REVIEW",
            "reason": "The lab room and exact group/period allocation are not clear.",
        },
        {
            "source_section": "5B",
            "target_section": "CSE 3B",
            "day": "THU",
            "source_row": "EVS",
            "status": "NEEDS_REVIEW",
            "reason": "No reliable faculty initial is associated with this grid cell.",
        },
        {
            "source_section": "5A/5B",
            "target_section": "CSE 3A/CSE 3B",
            "day": "SAT",
            "source_row": "PBL-MAD, placement activity, NSS/Yoga/workshop",
            "status": "NEEDS_REVIEW",
            "reason": "These are non-period Saturday activity blocks outside the requested Monday-Friday timetable.",
        },
    ]

    pdf_text: dict[str, str] = {}
    import pdfplumber

    with pdfplumber.open(PDF_PATH) as pdf:
        for page_number in range(3, min(6, len(pdf.pages)) + 1):
            page = pdf.pages[page_number - 1]
            text_content = page.extract_text(layout=False) or ""
            section_label = next(
                (label for label in ("5TH C", "5TH D", "5TH E", "5TH F") if label in text_content),
                f"PDF page {page_number}",
            )
            pdf_text[section_label] = text_content
    for section_label, text_content in pdf_text.items():
        unmapped_rows.append(
            {
                "source_section": section_label,
                "target_section": None,
                "status": "NEEDS_REVIEW",
                "reason": "Owner instructed that 5C-5F must not become new sections; no target section mapping was supplied.",
                "source_page_text": text_content,
            }
        )

    return room_conflicts, unmapped_rows


def create_configured_curricula(
    db: Session,
    faculty: dict[str, Faculty],
    subjects: dict[str, Subject],
    first_year_sections: dict[str, Section],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sections = db.query(Section).all()
    department_by_id = {dept.id: dept.name for dept in db.query(Department).all()}
    section_by_code = {section.code: section for section in sections}
    section_by_code.update(first_year_sections)
    relationships: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    schedule_entries: list[TimetableEntry] = []

    def synthetic_faculty_for(department: str) -> str:
        if department in {"CIVIL", "MECH", "FIRST_YEAR"}:
            return "engineering"
        if department == "ISE":
            return "ise"
        return "cse"

    mandatory = {
        ("CSE 1A", "python"): "swetha",
        ("CSE 1B", "python"): "swetha",
        ("CSE 2A", "edc"): "swetha",
        ("CSE 2B", "edc"): "swetha",
        ("CSE 2A", "dbms"): "swetha",
        ("CSE 2B", "dbms"): "swetha",
        ("CSE 2A", "daa"): "parvathish",
        ("CSE 2B", "daa"): "parvathish",
        ("CSE 3A", "ml"): "parvathish",
        ("CSE 3B", "ml"): "parvathish",
    }
    pdf_target_codes = {"CSE 3A", "CSE 3B"}
    fixed_first_year_slots = {
        ("CSE 1A", "cse1_math"): (0, "P1", "SH01"),
        ("CSE 1B", "cse1_math"): (0, "P2", "SH02"),
        ("CSE 1A", "cse1_physics"): (1, "P1", "SH01"),
        ("CSE 1B", "cse1_physics"): (1, "P2", "SH02"),
        ("CSE 1A", "python"): (2, "P1", "SH01"),
        ("CSE 1B", "python"): (2, "P2", "SH02"),
        ("CSE 1A", "cse1_english"): (3, "P1", "SH01"),
        ("CSE 1B", "cse1_english"): (3, "P2", "SH02"),
        ("CSE 1A", "cse1_chemistry"): (4, "P1", "SH01"),
        ("CSE 1B", "cse1_chemistry"): (4, "P2", "SH02"),
    }
    known_rooms = {
        room.code: room
        for room in db.query(Room).filter(Room.code.in_(["SH01", "SH02"])).all()
    }
    student_sections = {"CSE 1A", "CSE 1B"}

    for section_code, section in sorted(section_by_code.items()):
        dept_name = department_by_id.get(section.department_id, "")
        if section_code in pdf_target_codes:
            course_keys = ["fcg", "ml", "toc", "nexgen", "pecns", "mad", "rm", "evs"]
            theory_keys = ["fcg", "ml", "toc", "pecns", "mad"]
            lab_keys = ["nexgen"]
        else:
            template_data = CURRICULA_TEMPLATES.get(
                (section.department_id, section.year)
            )
            if template_data is None:
                raise RuntimeError(f"No configured curriculum for {section_code}.")
            course_keys = template_data["subjects"]
            theory_keys = template_data["theory"]
            lab_keys = template_data["labs"]

        for course_key in course_keys:
            faculty_key = mandatory.get((section_code, course_key))
            if faculty_key is None:
                faculty_key = synthetic_faculty_for(dept_name)
            course = SUBJECTS[course_key]
            relationship = {
                "faculty_id": faculty[faculty_key].id,
                "faculty_name": faculty[faculty_key].name,
                "subject_id": course["id"],
                "subject_code": course["code"],
                "subject_name": course["name"],
                "section_id": section.id,
                "section": section.code,
                "year": section.year,
                "provenance": "SYNTHETIC_CONFIGURED",
                "note": "Section-level teaching allocation is configured demo data, not an owner-provided fact.",
            }
            if section_code in pdf_target_codes and course_key in course_keys:
                # The imported source relationships are stored on the actual PDF entries.
                if course_key == "ml":
                    relationships.append(relationship)
                    unresolved.append(
                        {
                            **relationship,
                            "requested_weekly_periods": 1,
                            "status": "UNRESOLVED",
                            "reason": "Parvathish's configured ML assignment is separate from the PDF-listed ML faculty; no additional room-safe period is available without inventing a placement.",
                        }
                    )
                continue

            relationships.append(relationship)
            if (section_code, course_key) in fixed_first_year_slots:
                weekday, slot, room_code = fixed_first_year_slots[(section_code, course_key)]
                schedule_faculty = (
                    "swetha" if course_key == "python" else "engineering"
                )
                room = known_rooms[room_code]
                schedule_entries.append(
                    TimetableEntry(
                        id=f"syn_{section.id}_{course_key}",
                        section_id=section.id,
                        subject_id=subjects[course_key].id,
                        faculty_id=faculty[schedule_faculty].id,
                        weekday=weekday,
                        start_slot=slot,
                        duration_slots=1,
                        kind="THEORY",
                        required_room_type="CLASSROOM",
                        required_lab_kind=None,
                        required_facilities=[],
                        base_room_id=room.id,
                        provenance="SYNTHETIC",
                    )
                )
            elif course_key in theory_keys:
                unresolved.append(
                    {
                        **relationship,
                        "requested_weekly_periods": 1,
                        "status": "UNRESOLVED",
                        "reason": (
                            "No safely usable known-capacity regular classroom is "
                            "provided for this section. Remaining classroom capacities "
                            "are NULL; SH01/SH02 are owner-designated for first-year "
                            "CSE/seminar use, not assigned across this curriculum."
                        ),
                    }
                )
            elif course_key in lab_keys:
                unresolved.append(
                    {
                        **relationship,
                        "requested_weekly_periods": 1,
                        "status": "UNRESOLVED",
                        "reason": (
                            "Relevant lab room capacity is unknown (NULL); the hard "
                            "capacity rule prevents assigning this lab block."
                        ),
                    }
                )
            else:
                unresolved.append(
                    {
                        **relationship,
                        "requested_weekly_periods": 0,
                        "status": "CURRICULUM_ONLY",
                        "reason": "Included in the synthetic curriculum; no additional weekly period was requested to keep the section near five theory periods.",
                    }
                )

    for entry in schedule_entries:
        db.add(entry)
    db.flush()
    return relationships, unresolved


def main() -> None:
    require_target_database()
    import pdfplumber

    with pdfplumber.open(PDF_PATH) as pdf:
        if len(pdf.pages) != 6:
            raise SystemExit(f"Expected the known six-page timetable PDF; found {len(pdf.pages)} pages.")
    source_hash = hashlib.sha256(PDF_PATH.read_bytes()).hexdigest()

    with Session(engine) as db, db.begin():
        require_expected_state(db)
        first_year_sections = create_first_year_sections(db)
        faculty = create_faculty(db)
        subjects = create_subjects(db)

        pdf_room_conflicts, unmapped_pdf_rows = import_pdf_rows(db, faculty, subjects)
        relationships, unresolved_synthetic = create_configured_curricula(
            db, faculty, subjects, first_year_sections
        )

        review = {
            "source_pdf": "data/FFINAL-5th  SEM CSE TT.pdf",
            "source_sha256": source_hash,
            "mapping": {
                "5A": "CSE 3A",
                "5B": "CSE 3B",
                "5C-5F": "NEEDS_REVIEW; not created as sections",
            },
            "imported_pdf_entry_count": len(PDF_ROWS),
            "pdf_room_conflicts": pdf_room_conflicts,
            "unmapped_pdf_rows": unmapped_pdf_rows,
            "source_room_master_conflicts": {
                "5A": {
                    "pdf_room": "202",
                    "master_candidate": "A202",
                    "master_department": "ISE",
                    "master_floor": 2,
                },
                "5B": {
                    "pdf_room": "203",
                    "master_candidate": "A203",
                    "master_department": "ISE",
                    "master_floor": 2,
                },
                "lab_rooms": [
                    {"pdf_room": "210", "status": "NEEDS_REVIEW", "reason": "No A210 exists in the owner-provided master."},
                    {"pdf_room": "206", "status": "NEEDS_REVIEW", "reason": "A206 is owner-provided as an ISE classroom, not a lab."},
                    {"pdf_room": "305", "status": "NEEDS_REVIEW", "reason": "A305 is owner-provided as the Cyber 2 classroom, not a lab."},
                    {"pdf_room": "506", "status": "NEEDS_REVIEW", "reason": "A506 is owner-confirmed empty."},
                ],
            },
        }
        settings_values = [
            (
                "competition_timetable_review",
                "setting_competition_timetable_review",
                review,
            ),
            (
                "competition_synthetic_schedule_unresolved",
                "setting_synthetic_schedule_unresolved",
                unresolved_synthetic,
            ),
            (
                "competition_teaching_relationships",
                "setting_competition_teaching_relationships",
                relationships,
            ),
            (
                "competition_faculty_provenance",
                "setting_competition_faculty_provenance",
                {
                    **{
                        f"faculty_{key}": "REAL_TIMETABLE_PDF"
                        for key in PDF_FACULTY
                    },
                    "faculty_swetha": "REAL",
                    "faculty_parvathish": "REAL",
                    **{
                        f"faculty_{key}": "SYNTHETIC"
                        for key in SYNTHETIC_FACULTY
                    },
                },
            ),
        ]
        for key, setting_id, value in settings_values:
            db.add(Setting(id=setting_id, key=key, value=value))

    print(
        "Added only to campus_demo.db: 15 faculty (10 PDF-sourced, 2 owner-named, "
        "3 SYNTHETIC); configured curricula and relationships; 34 "
        "REAL_TIMETABLE_PDF timetable entries with unresolved rooms; and 10 "
        "room-assigned SYNTHETIC first-year CSE periods."
    )
    print(
        "Other generated periods/labs are recorded as UNRESOLVED where safe "
        "known-capacity rooms are unavailable; no room capacity was invented."
    )


if __name__ == "__main__":
    main()
