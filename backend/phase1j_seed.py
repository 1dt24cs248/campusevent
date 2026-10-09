import os
from datetime import datetime

from app.db import Base, engine, SessionLocal
from app.models.identity import User
from app.models.academic import Department, Section, Subject, Faculty, Student
from app.models.campus import Block, Floor, Room
from app.models.schedule import TimetableEntry
from app.models.scenario import PublishedVersion
from app.security import get_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'phase1j-e2e.sqlite')
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    for suffix in ['-wal', '-shm', '-journal']:
        p = DB_PATH + suffix
        if os.path.exists(p):
            os.remove(p)

# Ensure the environment-backed database URL is used before import; setting it here is safe for this script.

Base.metadata.create_all(bind=engine)
db = SessionLocal()

users = [
    {"id": "mgmt_validation", "email": "mgmt.validation@campus.local", "role": "MANAGEMENT", "display_name": "Validation Manager"},
    {"id": "student_validation", "email": "student.validation@campus.local", "role": "STUDENT", "display_name": "Validation Student"},
    {"id": "faculty_validation", "email": "faculty.validation@campus.local", "role": "FACULTY", "display_name": "Validation Faculty"},
]
for u in users:
    db.add(User(id=u["id"], email=u["email"], role=u["role"], display_name=u["display_name"], hashed_password=get_password_hash("Demo@1234"), active=True))

db.commit()

if not db.query(Department).filter(Department.id == "dept_cse").first():
    db.add(Department(id="dept_cse", name="CSE"))

if not db.query(Block).filter(Block.id == "block_validation").first():
    db.add(Block(id="block_validation", code="V", name="Validation Block", is_active=True, is_pilot=True))
if not db.query(Floor).filter(Floor.id == "floor_validation_1").first():
    db.add(Floor(id="floor_validation_1", block_id="block_validation", level=1, name="Floor 1", label="F1"))
if not db.query(Floor).filter(Floor.id == "floor_validation_2").first():
    db.add(Floor(id="floor_validation_2", block_id="block_validation", level=2, name="Floor 2", label="F2"))

db.commit()

if not db.query(Room).filter(Room.id == "room_proj_valid").first():
    db.add(Room(id="room_proj_valid", block_id="block_validation", floor_id="floor_validation_1", code="V101", display_name="V101", resource_type="CLASSROOM", capacity=70, allocatable_for_classes=True, reservable_for_events=False, facilities=["PROJECTOR","WHITEBOARD"], accessible=True, status="ACTIVE", is_spare=False, provenance="SYNTHETIC"))
if not db.query(Room).filter(Room.id == "room_noproj_valid").first():
    db.add(Room(id="room_noproj_valid", block_id="block_validation", floor_id="floor_validation_1", code="V102", display_name="V102", resource_type="CLASSROOM", capacity=70, allocatable_for_classes=True, reservable_for_events=False, facilities=["WHITEBOARD"], accessible=True, status="ACTIVE", is_spare=False, provenance="SYNTHETIC"))
if not db.query(Room).filter(Room.id == "room_alt_valid").first():
    db.add(Room(id="room_alt_valid", block_id="block_validation", floor_id="floor_validation_2", code="V201", display_name="V201", resource_type="CLASSROOM", capacity=80, allocatable_for_classes=True, reservable_for_events=False, facilities=["PROJECTOR","WHITEBOARD"], accessible=True, status="ACTIVE", is_spare=False, provenance="SYNTHETIC"))
db.commit()

if not db.query(Section).filter(Section.id == "sec_3cse_a_validation").first():
    db.add(Section(id="sec_3cse_a_validation", department_id="dept_cse", code="3CSE-A", name="3rd Sem CSE-A", year=3, strength=60, strength_provenance="SYNTHETIC", home_room_id="room_proj_valid", is_synthetic=True, provenance="SYNTHETIC"))
if not db.query(Subject).filter(Subject.id == "sub_cse_101_validation").first():
    db.add(Subject(id="sub_cse_101_validation", code="CSE101", name="Algorithms", description="Algorithm design", credits=4, department_id="dept_cse", kind="THEORY", required_facilities=["PROJECTOR"], lab_kind=None, is_synthetic=True))
db.commit()

faculty_user = db.query(User).filter(User.email == "faculty.validation@campus.local").first()
student_user = db.query(User).filter(User.email == "student.validation@campus.local").first()
if not db.query(Faculty).filter(Faculty.id == "faculty_validation_1").first():
    db.add(Faculty(id="faculty_validation_1", user_id=faculty_user.id, department_id="dept_cse", name="Validation Faculty", employee_id="EMP-VAL-001", designation="Assistant Professor"))
if not db.query(Student).filter(Student.id == "student_validation_1").first():
    db.add(Student(id="student_validation_1", user_id=student_user.id, section_id="sec_3cse_a_validation", usn="VAL-001", phone="9999999999", program="B.E. Computer Science & Engineering", semester=3, admission_year=2024, academic_status="ACTIVE", profile={"batch": "2024"}, anon_code="SV-001"))
db.commit()

if not db.query(TimetableEntry).filter(TimetableEntry.id == "entry_projector_validation").first():
    db.add(TimetableEntry(
        id="entry_projector_validation",
        section_id="sec_3cse_a_validation",
        subject_id="sub_cse_101_validation",
        faculty_id="faculty_validation_1",
        weekday=1,
        start_slot="P3",
        duration_slots=2,
        kind="THEORY",
        required_room_type="CLASSROOM",
        required_lab_kind=None,
        required_facilities=["PROJECTOR"],
        base_room_id="room_proj_valid",
        provenance="SYNTHETIC"
    ))
if not db.query(TimetableEntry).filter(TimetableEntry.id == "entry_nonprojector_validation").first():
    db.add(TimetableEntry(
        id="entry_nonprojector_validation",
        section_id="sec_3cse_a_validation",
        subject_id="sub_cse_101_validation",
        faculty_id="faculty_validation_1",
        weekday=1,
        start_slot="P5",
        duration_slots=1,
        kind="THEORY",
        required_room_type="CLASSROOM",
        required_lab_kind=None,
        required_facilities=[],
        base_room_id="room_alt_valid",
        provenance="SYNTHETIC"
    ))

mgmt_user = db.query(User).filter(User.email == "mgmt.validation@campus.local").first()
if not db.query(PublishedVersion).filter(PublishedVersion.id == "version_validation_v1").first():
    db.add(PublishedVersion(id="version_validation_v1", version_no=1, scenario_id=None, published_by=mgmt_user.id, summary="Validation baseline", published_at=datetime.utcnow()))

db.commit()
print('SEED_OK')
