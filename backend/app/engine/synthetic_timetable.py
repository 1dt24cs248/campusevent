"""Synthetic timetable generator and subject/faculty seed."""
import uuid
import random
import logging
from sqlalchemy.orm import Session
from app.models.academic import Subject, Faculty, Student, Section, Department
from app.models.schedule import TimetableEntry
from app.models.campus import Room
from app.engine.slots import PERIOD_SLOTS, LAB_BLOCK_PAIRS, get_slots_for_day

logger = logging.getLogger(__name__)

# Subject templates per department
DEPT_SUBJECTS = {
    "CSE": [
        ("DBMS", "Database Management Systems", "THEORY"),
        ("DAA", "Design & Analysis of Algorithms", "THEORY"),
        ("OS", "Operating Systems", "THEORY"),
        ("CN", "Computer Networks", "THEORY"),
        ("MAD", "Mobile App Development", "THEORY"),
        ("CSE-LAB", "CSE Lab", "LAB"),
    ],
    "ISE": [
        ("SE", "Software Engineering", "THEORY"),
        ("WEB", "Web Technology", "THEORY"),
        ("CC", "Cloud Computing", "THEORY"),
        ("AI", "Artificial Intelligence", "THEORY"),
        ("ISE-LAB", "ISE Lab", "LAB"),
    ],
    "MECH": [
        ("TD", "Thermodynamics", "THEORY"),
        ("FM", "Fluid Mechanics", "THEORY"),
        ("DOM", "Dynamics of Machinery", "THEORY"),
        ("ME-LAB", "Mech Lab", "LAB"),
    ],
    "CIVIL": [
        ("SOM", "Strength of Materials", "THEORY"),
        ("SUR", "Surveying", "THEORY"),
        ("GEO", "Geotechnical Engineering", "THEORY"),
        ("CV-LAB", "Civil Lab", "LAB"),
    ],
    "DS": [
        ("ML", "Machine Learning", "THEORY"),
        ("BDA", "Big Data Analytics", "THEORY"),
        ("STATS", "Statistics", "THEORY"),
        ("DV", "Data Visualization", "THEORY"),
        ("DS-LAB", "DS Lab", "LAB"),
    ],
    "AIML": [
        ("DL", "Deep Learning", "THEORY"),
        ("NLP", "Natural Language Processing", "THEORY"),
        ("CV", "Computer Vision", "THEORY"),
        ("RL", "Reinforcement Learning", "THEORY"),
        ("AI-LAB", "AIML Lab", "LAB"),
    ],
    "FIRST_YEAR": [
        ("MATH", "Engineering Mathematics", "THEORY"),
        ("PHY", "Engineering Physics", "THEORY"),
        ("CHEM", "Engineering Chemistry", "THEORY"),
        ("BEE", "Basic Electrical Engineering", "THEORY"),
        ("PCD", "Programming in C", "THEORY"),
        ("PHY-LAB", "Physics Lab", "LAB"),
        ("CHEM-LAB", "Chemistry Lab", "LAB"),
    ],
}

# Lab kind mapping
LAB_KIND_MAP = {
    "CSE-LAB": "CSE", "ISE-LAB": "ISE", "ME-LAB": "MECH_CIVIL",
    "CV-LAB": "MECH_CIVIL", "DS-LAB": "DS", "AI-LAB": "AIML",
    "PHY-LAB": "PHYSICS", "CHEM-LAB": "CHEMISTRY",
}


def generate_synthetic_timetable(db: Session):
    """Generate subjects, faculty, student records, and a synthetic timetable."""
    random.seed(42)  # Deterministic

    sections = db.query(Section).all()
    departments = {d.name: d for d in db.query(Department).all()}

    # 1. Create subjects
    existing_subjects = {s.code: s for s in db.query(Subject).all()}
    all_subjects = {}
    for dept_name, subj_list in DEPT_SUBJECTS.items():
        dept = departments.get(dept_name)
        if not dept:
            continue
        for code, name, kind in subj_list:
            full_code = f"{dept_name}-{code}"
            if full_code not in existing_subjects:
                subj = Subject(
                    id=f"subj_{full_code.lower().replace('-', '_')}",
                    code=full_code,
                    name=name,
                    department_id=dept.id,
                    kind=kind,
                    required_facilities=["PROJECTOR"] if kind == "THEORY" else ["LAB_EQUIPMENT"],
                    lab_kind=LAB_KIND_MAP.get(code),
                    is_synthetic=True,
                )
                db.add(subj)
                all_subjects[full_code] = subj
            else:
                all_subjects[full_code] = existing_subjects[full_code]
    db.flush()

    # 2. Create faculty
    existing_faculty = {f.id: f for f in db.query(Faculty).all()}
    faculty_pool = {}
    fac_counter = {}
    for dept_name in DEPT_SUBJECTS:
        dept = departments.get(dept_name)
        if not dept:
            continue
        fac_counter[dept_name] = 0
        faculty_pool[dept_name] = []
        needed = max(6, len([s for s in sections if s.department_id == dept.id]) * 2)
        for i in range(1, needed + 1):
            fac_id = f"fac_{dept_name.lower()}_{i:02d}"
            if fac_id not in existing_faculty:
                # Link demo faculty users if available
                user_id = None
                if dept_name == "CSE" and i == 1:
                    user_id = "user_faculty_cse1"
                elif dept_name == "CSE" and i == 2:
                    user_id = "user_faculty_cse2"
                elif dept_name == "ISE" and i == 1:
                    user_id = "user_faculty_ise1"
                fac = Faculty(
                    id=fac_id,
                    user_id=user_id,
                    department_id=dept.id,
                    name=f"Faculty {dept_name}-{i:02d}",
                    is_synthetic=True,
                )
                db.add(fac)
                faculty_pool[dept_name].append(fac)
            else:
                faculty_pool[dept_name].append(existing_faculty[fac_id])
    db.flush()

    # 3. Create student records for demo users
    existing_students = {s.id for s in db.query(Student).all()}
    demo_student_map = {
        "user_student_3csea": "sec_3cse_a",
        "user_student_2cseb": "sec_2cse_b",
        "user_student_1a": "sec_1_a",
    }
    for user_id, sec_id in demo_student_map.items():
        stud_id = f"student_{user_id}"
        if stud_id not in existing_students:
            section = db.query(Section).filter(Section.id == sec_id).first()
            if section:
                db.add(Student(
                    id=stud_id,
                    user_id=user_id,
                    section_id=sec_id,
                    anon_code=f"S-{uuid.uuid4().hex[:6].upper()}"
                ))
    db.flush()

    # 4. Generate timetable entries
    if db.query(TimetableEntry).count() > 0:
        logger.info("Timetable entries already exist, skipping generation")
        return

    # Track occupancy to avoid conflicts
    # Key: (weekday, slot) -> set of faculty_ids
    faculty_busy = {}
    # Key: (weekday, slot) -> set of section_ids
    section_busy = {}
    # Key: (weekday, slot) -> set of room_ids
    room_busy = {}

    rooms = db.query(Room).filter(Room.allocatable_for_classes == True).all()
    room_by_id = {r.id: r for r in rooms}

    entry_count = 0
    for section in sections:
        dept = db.query(Department).filter(Department.id == section.department_id).first()
        if not dept:
            continue
        dept_name = dept.name
        dept_subs = [s for c, s in all_subjects.items() if c.startswith(f"{dept_name}-")]
        theory_subs = [s for s in dept_subs if s.kind == "THEORY"]
        lab_subs = [s for s in dept_subs if s.kind == "LAB"]
        dept_faculty = faculty_pool.get(dept_name, [])
        if not dept_faculty:
            continue

        # Assign faculty round-robin to subjects
        sub_faculty = {}
        fi = 0
        for subj in dept_subs:
            sub_faculty[subj.id] = dept_faculty[fi % len(dept_faculty)]
            fi += 1

        # Generate ~5 theory classes per day (Mon-Fri), density ~0.65
        for weekday in range(6):  # 0=Mon to 5=Sat
            day_slots = get_slots_for_day(weekday)
            if not day_slots:
                continue

            # Theory slots: aim for ~65% occupancy
            theory_target = int(len(day_slots) * 0.65)
            if weekday == 5:
                theory_target = min(theory_target, 2)

            available_theory_slots = list(day_slots)
            random.shuffle(available_theory_slots)

            placed_theory = 0
            for slot in available_theory_slots:
                if placed_theory >= theory_target:
                    break
                subj = theory_subs[placed_theory % len(theory_subs)] if theory_subs else None
                if not subj:
                    break
                fac = sub_faculty.get(subj.id)
                if not fac:
                    continue

                key = (weekday, slot)
                if key not in faculty_busy:
                    faculty_busy[key] = set()
                if key not in section_busy:
                    section_busy[key] = set()
                if key not in room_busy:
                    room_busy[key] = set()

                if fac.id in faculty_busy[key] or section.id in section_busy[key]:
                    continue

                base_room_id = section.home_room_id
                if base_room_id and base_room_id in room_busy[key]:
                    # Try to find alternative room
                    alt = None
                    for r in rooms:
                        if (r.resource_type == "CLASSROOM" and r.id not in room_busy[key]
                                and r.capacity and r.capacity >= section.strength):
                            alt = r.id
                            break
                    if alt:
                        base_room_id = alt
                    else:
                        continue

                if base_room_id and base_room_id in room_busy[key]:
                    continue

                entry = TimetableEntry(
                    id=f"tt_{uuid.uuid4().hex[:12]}",
                    section_id=section.id,
                    subject_id=subj.id,
                    faculty_id=fac.id,
                    weekday=weekday,
                    start_slot=slot,
                    duration_slots=1,
                    kind="THEORY",
                    required_room_type="CLASSROOM",
                    required_facilities=["PROJECTOR"],
                    base_room_id=base_room_id,
                    provenance="SYNTHETIC",
                )
                db.add(entry)
                faculty_busy[key].add(fac.id)
                section_busy[key].add(section.id)
                if base_room_id:
                    room_busy[key].add(base_room_id)
                placed_theory += 1
                entry_count += 1

            # Lab: 1 lab block per week (Mon-Fri only)
            if weekday < 5 and lab_subs and weekday % 3 == 0:
                lab_subj = lab_subs[0]
                lab_fac = sub_faculty.get(lab_subj.id)
                if lab_fac:
                    for s1, s2 in LAB_BLOCK_PAIRS:
                        if s1 not in day_slots or s2 not in day_slots:
                            continue
                        k1 = (weekday, s1)
                        k2 = (weekday, s2)
                        for k in [k1, k2]:
                            if k not in faculty_busy:
                                faculty_busy[k] = set()
                            if k not in section_busy:
                                section_busy[k] = set()
                            if k not in room_busy:
                                room_busy[k] = set()

                        if (lab_fac.id in faculty_busy[k1] or lab_fac.id in faculty_busy[k2]
                                or section.id in section_busy[k1] or section.id in section_busy[k2]):
                            continue

                        # Find a lab room
                        lab_room_id = None
                        lab_kind = lab_subj.lab_kind
                        for r in rooms:
                            if r.resource_type == "LAB":
                                if lab_kind and r.lab_kind and r.lab_kind != lab_kind:
                                    continue
                                if r.id not in room_busy[k1] and r.id not in room_busy[k2]:
                                    lab_room_id = r.id
                                    break

                        if not lab_room_id:
                            continue

                        entry = TimetableEntry(
                            id=f"tt_{uuid.uuid4().hex[:12]}",
                            section_id=section.id,
                            subject_id=lab_subj.id,
                            faculty_id=lab_fac.id,
                            weekday=weekday,
                            start_slot=s1,
                            duration_slots=2,
                            kind="LAB",
                            required_room_type="LAB",
                            required_lab_kind=lab_kind,
                            required_facilities=["LAB_EQUIPMENT"],
                            base_room_id=lab_room_id,
                            provenance="SYNTHETIC",
                        )
                        db.add(entry)
                        faculty_busy[k1].add(lab_fac.id)
                        faculty_busy[k2].add(lab_fac.id)
                        section_busy[k1].add(section.id)
                        section_busy[k2].add(section.id)
                        room_busy[k1].add(lab_room_id)
                        room_busy[k2].add(lab_room_id)
                        entry_count += 1
                        break

    db.commit()
    logger.info(f"Generated {entry_count} timetable entries")
