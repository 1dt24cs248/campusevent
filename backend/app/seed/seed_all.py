from app.db import Base, engine, SessionLocal
from app.models.identity import User
from app.models.academic import Department, Section
from app.security import get_password_hash
from app.seed.blockA import seed_block_a
from app.identity_schema import migrate_identity_columns
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_users(db):
    users_data = [
        {"id": "user_management", "email": "management@demo.local", "role": "MANAGEMENT", "display_name": "Campus Manager"},
        {"id": "user_student_3csea", "email": "student.3cse-a@demo.local", "role": "STUDENT", "display_name": "Student 3CSE-A"},
        {"id": "user_student_2cseb", "email": "student.2cse-b@demo.local", "role": "STUDENT", "display_name": "Student 2CSE-B"},
        {"id": "user_student_1a", "email": "student.1a@demo.local", "role": "STUDENT", "display_name": "Student 1-A"},
        {"id": "user_faculty_cse1", "email": "faculty.cse1@demo.local", "role": "FACULTY", "display_name": "Faculty CSE-01"},
        {"id": "user_faculty_cse2", "email": "faculty.cse2@demo.local", "role": "FACULTY", "display_name": "Faculty CSE-02"},
        {"id": "user_faculty_ise1", "email": "faculty.ise1@demo.local", "role": "FACULTY", "display_name": "Faculty ISE-01"},
        {"id": "user_maintenance", "email": "maintenance@demo.local", "role": "MAINTENANCE", "display_name": "Maintenance Staff"},
        {"id": "user_safety", "email": "safety@demo.local", "role": "SAFETY", "display_name": "Safety Officer", "can_view_incidents": True}
    ]
    
    hashed_pwd = get_password_hash("Demo@1234")
    for u in users_data:
        existing = db.query(User).filter(User.email == u["email"]).first()
        if not existing:
            user = User(
                id=u["id"],
                email=u["email"],
                hashed_password=hashed_pwd,
                role=u["role"],
                display_name=u.get("display_name"),
                can_view_incidents=u.get("can_view_incidents", False)
            )
            db.add(user)
    db.commit()

def seed_departments(db):
    depts = ["CSE", "ISE", "MECH", "CIVIL", "DS", "AIML", "FIRST_YEAR"]
    for d in depts:
        existing = db.query(Department).filter(Department.name == d).first()
        if not existing:
            db.add(Department(id=f"dept_{d}", name=d))
    db.commit()

def seed_sections(db):
    import json, os
    # Load from sections.json for accurate data
    sections_json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'data', 'sections.json')
    with open(sections_json_path, 'r') as f:
        sections_data = json.load(f)
    
    for s in sections_data:
        sec_id = f"sec_{s['code'].lower().replace('-', '_')}"
        existing = db.query(Section).filter(Section.id == sec_id).first()
        if not existing:
            dept = db.query(Department).filter(Department.name == s["department"]).first()
            if dept:
                from app.models.campus import Room
                home_room = db.query(Room).filter(Room.code == s["home_room"]).first()
                sec = Section(
                    id=sec_id,
                    department_id=dept.id,
                    code=s["code"],
                    name=s["name"],
                    year=s["year"],
                    strength=s["strength"],
                    strength_provenance=s.get("strength_provenance", "SYNTHETIC"),
                    home_room_id=home_room.id if home_room else None,
                    is_synthetic=s.get("is_synthetic", True),
                    provenance=s.get("strength_provenance", "SYNTHETIC")
                )
                db.add(sec)
    db.commit()

def run_seed():
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    migrate_identity_columns(engine)
    
    db = SessionLocal()
    try:
        logger.info("Seeding Users...")
        seed_users(db)
        logger.info("Seeding Departments...")
        seed_departments(db)
        logger.info("Seeding Block A Campus Data...")
        seed_block_a(db)
        logger.info("Seeding Sections...")
        seed_sections(db)
        logger.info("Generating Synthetic Timetable...")
        from app.engine.synthetic_timetable import generate_synthetic_timetable
        generate_synthetic_timetable(db)
        logger.info("Seed complete.")
    except Exception as e:
        db.rollback()
        logger.error(f"Seeding failed: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    run_seed()
