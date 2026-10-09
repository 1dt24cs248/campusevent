import os

base_dir = r"c:\Users\Shailendra Kumar N\OneDrive\Desktop\campusevent\backend"

files = {
    "requirements.txt": """fastapi
uvicorn[standard]
sqlalchemy
pydantic
pydantic-settings
python-jose[cryptography]
passlib[bcrypt]
ortools
python-multipart
cryptography
pytz
""",
    ".env.example": """DATABASE_URL=sqlite:///./campus.db
JWT_SECRET=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
APP_ENCRYPTION_KEY=
DEMO_NOW=
""",
    "app/__init__.py": "",
    "app/config.py": """from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./campus.db"
    JWT_SECRET: str = "secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    APP_ENCRYPTION_KEY: str = ""
    DEMO_NOW: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra='ignore')

settings = Settings()
""",
    "app/db.py": """from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
""",
    "app/clock.py": """from datetime import datetime
import pytz
from app.config import settings

def get_now() -> datetime:
    if settings.DEMO_NOW:
        return datetime.fromisoformat(settings.DEMO_NOW)
    return datetime.now(pytz.timezone('Asia/Kolkata')).replace(tzinfo=None)
""",
    "app/audit.py": """from sqlalchemy.orm import Session
from app.models.identity import AuditLog
from app.clock import get_now

def log_audit(db: Session, user_id: str, action: str, entity_type: str, entity_id: str, details: dict):
    audit = AuditLog(
        id=f"audit_{int(get_now().timestamp()*1000)}",
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        timestamp=get_now()
    )
    db.add(audit)
""",
    "app/security.py": """from passlib.context import CryptContext
from datetime import timedelta
from jose import jwt
from app.config import settings
from app.clock import get_now

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    now = get_now()
    expire = now + (expires_delta if expires_delta else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.ALGORITHM)
""",
    "app/deps.py": """from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.config import settings
from app.models.identity import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user

def require_roles(roles: list[str]):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return current_user
    return role_checker
""",
    "app/main.py": """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, campus
from app.db import Base, engine

# Note: We rely on seed scripts to create tables, but doing it here just in case for development.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Campus Intelligence & Action Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(campus.router, prefix="/api", tags=["campus"])

@app.get("/health")
def health_check():
    return {"status": "ok"}
""",
    "app/models/__init__.py": """from app.models.campus import Block, Floor, Room
from app.models.academic import Department, Section, Subject, Faculty, Student
from app.models.schedule import TimetableEntry, SessionOverride, SectionStrengthHistory
from app.models.availability import RoomUnavailability
from app.models.scenario import Scenario, ScenarioChange, OptimizationRun, Approval, PublishedVersion
from app.models.workflow import Notification, NotificationRead
from app.models.operations import MaintenanceTicket, TicketHistory, Event, EventRoom, Opportunity, Announcement, Assessment, CampusFAQ
from app.models.safety import Incident, IncidentStatusHistory, EmergencyConfig, EmergencyEvent
from app.models.navigation import NavNode, NavEdge, NavConfig
from app.models.identity import User, AuditLog, Setting
""",
    "app/models/campus.py": """from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.db import Base

class Block(Base):
    __tablename__ = 'blocks'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    floors = relationship("Floor", back_populates="block")

class Floor(Base):
    __tablename__ = 'floors'
    id = Column(String, primary_key=True)
    block_id = Column(String, ForeignKey('blocks.id'))
    level = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    block = relationship("Block", back_populates="floors")
    rooms = relationship("Room", back_populates="floor")

class Room(Base):
    __tablename__ = 'rooms'
    id = Column(String, primary_key=True)
    block_id = Column(String, ForeignKey('blocks.id'))
    floor_id = Column(String, ForeignKey('floors.id'))
    code = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    aliases = Column(JSON, default=list)
    resource_type = Column(String, nullable=False)
    department = Column(String, nullable=True)
    capacity = Column(Integer, nullable=True)
    capacity_provenance = Column(String, nullable=True)
    allocatable_for_classes = Column(Boolean, default=True)
    reservable_for_events = Column(Boolean, default=False)
    lab_kind = Column(String, nullable=True)
    facilities = Column(JSON, default=list)
    accessible = Column(Boolean, nullable=True)
    status = Column(String, default='ACTIVE')
    is_spare = Column(Boolean, default=False)
    provenance = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    
    floor = relationship("Floor", back_populates="rooms")
    block = relationship("Block")
""",
    "app/models/academic.py": """from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.db import Base

class Department(Base):
    __tablename__ = 'departments'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)

class Section(Base):
    __tablename__ = 'sections'
    id = Column(String, primary_key=True)
    department_id = Column(String, ForeignKey('departments.id'))
    name = Column(String, nullable=False)
    strength = Column(Integer, nullable=False)
    home_room_id = Column(String, ForeignKey('rooms.id'), nullable=True)
    provenance = Column(String, nullable=True)

class Subject(Base):
    __tablename__ = 'subjects'
    id = Column(String, primary_key=True)
    code = Column(String, nullable=False)
    name = Column(String, nullable=False)
    department_id = Column(String, ForeignKey('departments.id'))

class Faculty(Base):
    __tablename__ = 'faculties'
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'))
    department_id = Column(String, ForeignKey('departments.id'))

class Student(Base):
    __tablename__ = 'students'
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'))
    section_id = Column(String, ForeignKey('sections.id'))
""",
    "app/models/schedule.py": """from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from app.db import Base

class TimetableEntry(Base):
    __tablename__ = 'timetable_entries'
    id = Column(String, primary_key=True)
    section_id = Column(String, ForeignKey('sections.id'))
    subject_id = Column(String, ForeignKey('subjects.id'))
    faculty_id = Column(String, ForeignKey('faculties.id'))
    room_id = Column(String, ForeignKey('rooms.id'))
    day_of_week = Column(Integer, nullable=False) # 1-7
    start_time = Column(String, nullable=False) # HH:MM
    end_time = Column(String, nullable=False)

class SessionOverride(Base):
    __tablename__ = 'session_overrides'
    id = Column(String, primary_key=True)
    timetable_entry_id = Column(String, ForeignKey('timetable_entries.id'))
    date = Column(DateTime, nullable=False)
    new_room_id = Column(String, ForeignKey('rooms.id'), nullable=True)
    new_faculty_id = Column(String, ForeignKey('faculties.id'), nullable=True)

class SectionStrengthHistory(Base):
    __tablename__ = 'section_strength_histories'
    id = Column(String, primary_key=True)
    section_id = Column(String, ForeignKey('sections.id'))
    recorded_at = Column(DateTime, nullable=False)
    strength = Column(Integer, nullable=False)
""",
    "app/models/availability.py": """from sqlalchemy import Column, String, DateTime, ForeignKey
from app.db import Base

class RoomUnavailability(Base):
    __tablename__ = 'room_unavailability'
    id = Column(String, primary_key=True)
    room_id = Column(String, ForeignKey('rooms.id'))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    reason = Column(String, nullable=False)
""",
    "app/models/scenario.py": """from sqlalchemy import Column, String, JSON, DateTime, Boolean, ForeignKey
from app.db import Base

class Scenario(Base):
    __tablename__ = 'scenarios'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)

class ScenarioChange(Base):
    __tablename__ = 'scenario_changes'
    id = Column(String, primary_key=True)
    scenario_id = Column(String, ForeignKey('scenarios.id'))
    change_type = Column(String, nullable=False)
    details = Column(JSON, nullable=False)

class OptimizationRun(Base):
    __tablename__ = 'optimization_runs'
    id = Column(String, primary_key=True)
    scenario_id = Column(String, ForeignKey('scenarios.id'))
    status = Column(String, nullable=False)
    results = Column(JSON, nullable=True)

class Approval(Base):
    __tablename__ = 'approvals'
    id = Column(String, primary_key=True)
    scenario_id = Column(String, ForeignKey('scenarios.id'))
    status = Column(String, nullable=False)

class PublishedVersion(Base):
    __tablename__ = 'published_versions'
    id = Column(String, primary_key=True)
    scenario_id = Column(String, ForeignKey('scenarios.id'))
    published_at = Column(DateTime, nullable=False)
""",
    "app/models/workflow.py": """from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from app.db import Base

class Notification(Base):
    __tablename__ = 'notifications'
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey('users.id'))
    content = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)

class NotificationRead(Base):
    __tablename__ = 'notification_reads'
    id = Column(String, primary_key=True)
    notification_id = Column(String, ForeignKey('notifications.id'))
    user_id = Column(String, ForeignKey('users.id'))
    read_at = Column(DateTime, nullable=False)
""",
    "app/models/operations.py": """from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from app.db import Base

class MaintenanceTicket(Base):
    __tablename__ = 'maintenance_tickets'
    id = Column(String, primary_key=True)
    room_id = Column(String, ForeignKey('rooms.id'))
    description = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)

class TicketHistory(Base):
    __tablename__ = 'ticket_histories'
    id = Column(String, primary_key=True)
    ticket_id = Column(String, ForeignKey('maintenance_tickets.id'))
    status = Column(String, nullable=False)
    changed_at = Column(DateTime, nullable=False)

class Event(Base):
    __tablename__ = 'events'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)

class EventRoom(Base):
    __tablename__ = 'event_rooms'
    id = Column(String, primary_key=True)
    event_id = Column(String, ForeignKey('events.id'))
    room_id = Column(String, ForeignKey('rooms.id'))

class Opportunity(Base):
    __tablename__ = 'opportunities'
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)

class Announcement(Base):
    __tablename__ = 'announcements'
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)

class Assessment(Base):
    __tablename__ = 'assessments'
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)

class CampusFAQ(Base):
    __tablename__ = 'campus_faqs'
    id = Column(String, primary_key=True)
    question = Column(String, nullable=False)
    answer = Column(String, nullable=False)
""",
    "app/models/safety.py": """from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from app.db import Base

class Incident(Base):
    __tablename__ = 'incidents'
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    status = Column(String, nullable=False)

class IncidentStatusHistory(Base):
    __tablename__ = 'incident_status_histories'
    id = Column(String, primary_key=True)
    incident_id = Column(String, ForeignKey('incidents.id'))
    status = Column(String, nullable=False)
    changed_at = Column(DateTime, nullable=False)

class EmergencyConfig(Base):
    __tablename__ = 'emergency_configs'
    id = Column(String, primary_key=True)
    config_data = Column(JSON, nullable=False)

class EmergencyEvent(Base):
    __tablename__ = 'emergency_events'
    id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    triggered_at = Column(DateTime, nullable=False)
""",
    "app/models/navigation.py": """from sqlalchemy import Column, String, Float, JSON
from app.db import Base

class NavNode(Base):
    __tablename__ = 'nav_nodes'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    z = Column(Float, nullable=False)

class NavEdge(Base):
    __tablename__ = 'nav_edges'
    id = Column(String, primary_key=True)
    node1_id = Column(String, nullable=False)
    node2_id = Column(String, nullable=False)
    distance = Column(Float, nullable=False)

class NavConfig(Base):
    __tablename__ = 'nav_configs'
    id = Column(String, primary_key=True)
    config_data = Column(JSON, nullable=False)
""",
    "app/models/identity.py": """from sqlalchemy import Column, String, DateTime, JSON
from app.db import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, nullable=False)

class Setting(Base):
    __tablename__ = 'settings'
    id = Column(String, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, nullable=False)
""",
    "app/schemas/__init__.py": "",
    "app/schemas/campus.py": """from pydantic import BaseModel
from typing import List, Optional

class RoomBase(BaseModel):
    id: str
    block_id: str
    floor_id: str
    code: str
    display_name: str
    aliases: List[str]
    resource_type: str
    department: Optional[str] = None
    capacity: Optional[int] = None
    capacity_provenance: Optional[str] = None
    allocatable_for_classes: bool
    reservable_for_events: bool
    lab_kind: Optional[str] = None
    facilities: List[str]
    accessible: Optional[bool] = None
    status: str
    is_spare: bool
    provenance: Optional[str] = None
    notes: Optional[str] = None

class RoomResponse(RoomBase):
    class Config:
        from_attributes = True

class FloorBase(BaseModel):
    id: str
    block_id: str
    level: int
    name: str

class FloorResponse(FloorBase):
    class Config:
        from_attributes = True

class BlockBase(BaseModel):
    id: str
    name: str

class BlockResponse(BlockBase):
    class Config:
        from_attributes = True
""",
    "app/schemas/auth.py": """from pydantic import BaseModel

class LoginRequest(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    
    class Config:
        from_attributes = True
""",
    "app/routers/__init__.py": "",
    "app/routers/auth.py": """from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.identity import User
from app.schemas.auth import Token, UserResponse
from app.security import verify_password, create_access_token
from app.deps import get_current_user

router = APIRouter(prefix="/auth")

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.id, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user
""",
    "app/routers/campus.py": """from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.deps import get_db
from app.models.campus import Block, Floor, Room
from app.schemas.campus import BlockResponse, FloorResponse, RoomResponse

router = APIRouter()

@router.get("/blocks", response_model=List[BlockResponse])
def get_blocks(db: Session = Depends(get_db)):
    return db.query(Block).all()

@router.get("/blocks/{id}/floors", response_model=List[FloorResponse])
def get_floors_for_block(id: str, db: Session = Depends(get_db)):
    block = db.query(Block).filter(Block.id == id).first()
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    return db.query(Floor).filter(Floor.block_id == id).all()

@router.get("/floors/{id}/rooms", response_model=List[RoomResponse])
def get_rooms_for_floor(id: str, db: Session = Depends(get_db)):
    floor = db.query(Floor).filter(Floor.id == id).first()
    if not floor:
        raise HTTPException(status_code=404, detail="Floor not found")
    return db.query(Room).filter(Room.floor_id == id).all()

@router.get("/rooms/{id}", response_model=RoomResponse)
def get_room(id: str, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.id == id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room
""",
    "app/seed/__init__.py": "",
    "app/seed/gen_keys.py": """import os
import secrets
from cryptography.fernet import Fernet

def generate_keys():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    jwt_secret = secrets.token_urlsafe(32)
    fernet_key = Fernet.generate_key().decode()
    
    env_content = ""
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            env_content = f.read()
    else:
        with open(env_path + ".example", 'r') as f:
            env_content = f.read()
            
    lines = env_content.split('\\n')
    new_lines = []
    has_jwt = False
    has_enc = False
    for line in lines:
        if line.startswith('JWT_SECRET='):
            new_lines.append(f'JWT_SECRET={jwt_secret}')
            has_jwt = True
        elif line.startswith('APP_ENCRYPTION_KEY='):
            new_lines.append(f'APP_ENCRYPTION_KEY={fernet_key}')
            has_enc = True
        else:
            new_lines.append(line)
            
    if not has_jwt:
        new_lines.append(f'JWT_SECRET={jwt_secret}')
    if not has_enc:
        new_lines.append(f'APP_ENCRYPTION_KEY={fernet_key}')
        
    with open(env_path, 'w') as f:
        f.write('\\n'.join(new_lines))
    print("Generated JWT_SECRET and APP_ENCRYPTION_KEY in .env")

if __name__ == "__main__":
    generate_keys()
""",
    "app/seed/seed_all.py": """from app.db import Base, engine, SessionLocal
from app.models.identity import User
from app.models.academic import Department, Section
from app.security import get_password_hash
from app.seed.blockA import seed_block_a
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_users(db):
    users_data = [
        {"id": "user_management", "email": "management@demo.local", "role": "MANAGEMENT"},
        {"id": "user_student_3csea", "email": "student.3cse-a@demo.local", "role": "STUDENT"},
        {"id": "user_student_2cseb", "email": "student.2cse-b@demo.local", "role": "STUDENT"},
        {"id": "user_student_1a", "email": "student.1a@demo.local", "role": "STUDENT"},
        {"id": "user_faculty_cse1", "email": "faculty.cse1@demo.local", "role": "FACULTY"},
        {"id": "user_faculty_cse2", "email": "faculty.cse2@demo.local", "role": "FACULTY"},
        {"id": "user_faculty_ise1", "email": "faculty.ise1@demo.local", "role": "FACULTY"},
        {"id": "user_maintenance", "email": "maintenance@demo.local", "role": "MAINTENANCE"},
        {"id": "user_safety", "email": "safety@demo.local", "role": "SAFETY"}
    ]
    
    hashed_pwd = get_password_hash("Demo@1234")
    for u in users_data:
        existing = db.query(User).filter(User.email == u["email"]).first()
        if not existing:
            user = User(
                id=u["id"],
                email=u["email"],
                hashed_password=hashed_pwd,
                role=u["role"]
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
    # This must run after blockA seed because it sets home_room_id
    sections_data = [
        {"id": "sec_2cse_a", "dept": "CSE", "name": "2CSE-A", "strength": 63, "home_room_id": "room_A101"},
        {"id": "sec_2cse_b", "dept": "CSE", "name": "2CSE-B", "strength": 67, "home_room_id": "room_A102"},
        {"id": "sec_2cse_c", "dept": "CSE", "name": "2CSE-C", "strength": 57, "home_room_id": "room_A103"},
        {"id": "sec_3cse_a", "dept": "CSE", "name": "3CSE-A", "strength": 63, "home_room_id": "room_A104"},
        {"id": "sec_3cse_b", "dept": "CSE", "name": "3CSE-B", "strength": 69, "home_room_id": "room_A105"},
        {"id": "sec_3cse_c", "dept": "CSE", "name": "3CSE-C", "strength": 58, "home_room_id": "room_A106"},
        {"id": "sec_4cse_a", "dept": "CSE", "name": "4CSE-A", "strength": 68, "home_room_id": "room_A107"},
        {"id": "sec_4cse_b", "dept": "CSE", "name": "4CSE-B", "strength": 70, "home_room_id": "room_A108"},
        
        {"id": "sec_1_a", "dept": "FIRST_YEAR", "name": "1-A", "strength": 66, "home_room_id": "room_B05"},
        {"id": "sec_1_b", "dept": "FIRST_YEAR", "name": "1-B", "strength": 68, "home_room_id": "room_SH-01"},
        {"id": "sec_1_c", "dept": "FIRST_YEAR", "name": "1-C", "strength": 70, "home_room_id": "room_SH-02"},
        
        {"id": "sec_2ise_a", "dept": "ISE", "name": "2ISE-A", "strength": 58, "home_room_id": "room_A201"},
        {"id": "sec_3ise_a", "dept": "ISE", "name": "3ISE-A", "strength": 60, "home_room_id": "room_A202"},
        {"id": "sec_4ise_a", "dept": "ISE", "name": "4ISE-A", "strength": 56, "home_room_id": "room_A203"},
        {"id": "sec_2ise_b", "dept": "ISE", "name": "2ISE-B", "strength": 59, "home_room_id": "room_A204"},
        
        {"id": "sec_2me_a", "dept": "MECH", "name": "2ME-A", "strength": 54, "home_room_id": "room_A301"},
        {"id": "sec_3me_a", "dept": "MECH", "name": "3ME-A", "strength": 57, "home_room_id": "room_A302"},
        {"id": "sec_2cv_a", "dept": "CIVIL", "name": "2CV-A", "strength": 50, "home_room_id": "room_A303"},
        {"id": "sec_3cv_a", "dept": "CIVIL", "name": "3CV-A", "strength": 55, "home_room_id": "room_A304"},
        
        {"id": "sec_2ds_a", "dept": "DS", "name": "2DS-A", "strength": 60, "home_room_id": "room_A401"},
        {"id": "sec_3ds_a", "dept": "DS", "name": "3DS-A", "strength": 58, "home_room_id": "room_A402"},
        {"id": "sec_4ds_a", "dept": "DS", "name": "4DS-A", "strength": 55, "home_room_id": "room_A403"},
        {"id": "sec_2ds_b", "dept": "DS", "name": "2DS-B", "strength": 59, "home_room_id": "room_A404"},
        
        {"id": "sec_2ai_a", "dept": "AIML", "name": "2AI-A", "strength": 60, "home_room_id": "room_A501"},
        {"id": "sec_3ai_a", "dept": "AIML", "name": "3AI-A", "strength": 58, "home_room_id": "room_A502"},
        {"id": "sec_4ai_a", "dept": "AIML", "name": "4AI-A", "strength": 57, "home_room_id": "room_A503"},
        {"id": "sec_3ai_b", "dept": "AIML", "name": "3AI-B", "strength": 60, "home_room_id": "room_A504"},
    ]
    
    for s in sections_data:
        existing = db.query(Section).filter(Section.id == s["id"]).first()
        if not existing:
            dept = db.query(Department).filter(Department.name == s["dept"]).first()
            if dept:
                sec = Section(
                    id=s["id"],
                    department_id=dept.id,
                    name=s["name"],
                    strength=s["strength"],
                    home_room_id=s["home_room_id"],
                    provenance="SYNTHETIC" if s["dept"] not in ["CSE", "FIRST_YEAR"] else "PROVIDED" if s["dept"] == "CSE" else "ESTIMATED"
                )
                db.add(sec)
    db.commit()

def run_seed():
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
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
        logger.info("Seed complete.")
    except Exception as e:
        db.rollback()
        logger.error(f"Seeding failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_seed()
""",
    "app/seed/blockA.py": """from app.models.campus import Block, Floor, Room

def seed_block_a(db):
    block = db.query(Block).filter(Block.id == "block_A").first()
    if not block:
        block = Block(id="block_A", name="Block A")
        db.add(block)
        db.commit()
    
    floors_data = [
        {"id": "floor_A_basement", "level": -1, "name": "Basement"},
        {"id": "floor_A_ground", "level": 0, "name": "Ground Floor"},
        {"id": "floor_A_1", "level": 1, "name": "1st Floor"},
        {"id": "floor_A_2", "level": 2, "name": "2nd Floor"},
        {"id": "floor_A_3", "level": 3, "name": "3rd Floor"},
        {"id": "floor_A_4", "level": 4, "name": "4th Floor"},
        {"id": "floor_A_5", "level": 5, "name": "5th Floor"},
    ]
    
    for f in floors_data:
        existing = db.query(Floor).filter(Floor.id == f["id"]).first()
        if not existing:
            db.add(Floor(id=f["id"], block_id="block_A", level=f["level"], name=f["name"]))
    db.commit()

    rooms_data = [
        # BASEMENT (-1)
        {"id": "room_SH-01", "floor_id": "floor_A_basement", "code": "SH-01", "display_name": "Seminar Hall 1", "type": "SEMINAR_HALL", "cap": 100, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR", "PA_SYSTEM"]},
        {"id": "room_SH-02", "floor_id": "floor_A_basement", "code": "SH-02", "display_name": "Seminar Hall 2", "type": "SEMINAR_HALL", "cap": 80, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR", "PA_SYSTEM"]},
        {"id": "room_B03", "floor_id": "floor_A_basement", "code": "B03", "display_name": "Classroom B03", "type": "CLASSROOM", "cap": 60, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_B04", "floor_id": "floor_A_basement", "code": "B04", "display_name": "Classroom B04", "type": "CLASSROOM", "cap": 55, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_B05", "floor_id": "floor_A_basement", "code": "B05", "display_name": "Classroom B05", "type": "CLASSROOM", "cap": 70, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_aiml_lab", "floor_id": "floor_A_basement", "code": "AIML Lab", "display_name": "AIML Lab", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "AIML", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_phy_lab", "floor_id": "floor_A_basement", "code": "Physics Lab", "display_name": "Physics Lab", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "PHYSICS", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_chem_lab", "floor_id": "floor_A_basement", "code": "Chemistry Lab", "display_name": "Chemistry Lab", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "CHEMISTRY", "fac": ["LAB_EQUIPMENT"]},
        
        # GROUND FLOOR (0)
        {"id": "room_prin_off", "floor_id": "floor_A_ground", "code": "Principal Office", "display_name": "Principal Office", "type": "OFFICE", "cap": None, "prov": None, "alloc": False, "res": False, "fac": []},
        {"id": "room_adm_block", "floor_id": "floor_A_ground", "code": "Admission Block", "display_name": "Admission Block", "type": "OFFICE", "cap": None, "prov": None, "alloc": False, "res": False, "fac": []},
        {"id": "room_enq_off", "floor_id": "floor_A_ground", "code": "Enquiry Office", "display_name": "Enquiry Office", "type": "OFFICE", "cap": None, "prov": None, "alloc": False, "res": False, "fac": []},
        {"id": "room_meet_hall", "floor_id": "floor_A_ground", "code": "Meeting Hall", "display_name": "Meeting Hall", "type": "MEETING_HALL", "cap": None, "prov": None, "alloc": False, "res": True, "fac": []},
        
        # 1ST FLOOR (1)
        {"id": "room_A101", "floor_id": "floor_A_1", "code": "A101", "display_name": "Classroom A101", "type": "CLASSROOM", "cap": 60, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A102", "floor_id": "floor_A_1", "code": "A102", "display_name": "Classroom A102", "type": "CLASSROOM", "cap": 65, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A103", "floor_id": "floor_A_1", "code": "A103", "display_name": "Classroom A103", "type": "CLASSROOM", "cap": 50, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A104", "floor_id": "floor_A_1", "code": "A104", "display_name": "Classroom A104", "type": "CLASSROOM", "cap": 55, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A105", "floor_id": "floor_A_1", "code": "A105", "display_name": "Classroom A105", "type": "CLASSROOM", "cap": 70, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A106", "floor_id": "floor_A_1", "code": "A106", "display_name": "Classroom A106", "type": "CLASSROOM", "cap": 60, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A107", "floor_id": "floor_A_1", "code": "A107", "display_name": "Classroom A107", "type": "CLASSROOM", "cap": 65, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A108", "floor_id": "floor_A_1", "code": "A108", "display_name": "Classroom A108", "type": "CLASSROOM", "cap": 55, "prov": "PROVIDED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_cse_lab_1", "floor_id": "floor_A_1", "code": "CSE Lab 1", "display_name": "CSE Lab 1", "type": "LAB", "cap": 35, "prov": "PROVIDED", "alloc": True, "res": False, "lab_kind": "CSE", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_cse_lab_2", "floor_id": "floor_A_1", "code": "CSE Lab 2", "display_name": "CSE Lab 2", "type": "LAB", "cap": 35, "prov": "PROVIDED", "alloc": True, "res": False, "lab_kind": "CSE", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_A1_SPARE", "floor_id": "floor_A_1", "code": "A1-SPARE", "display_name": "Spare A1", "type": "CLASSROOM", "cap": 60, "prov": "ESTIMATED", "alloc": True, "res": False, "is_spare": True, "fac": ["PROJECTOR"]},

        # 2ND FLOOR (2)
        {"id": "room_A201", "floor_id": "floor_A_2", "code": "A201", "display_name": "Classroom A201", "type": "CLASSROOM", "cap": 65, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A202", "floor_id": "floor_A_2", "code": "A202", "display_name": "Classroom A202", "type": "CLASSROOM", "cap": 60, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A203", "floor_id": "floor_A_2", "code": "A203", "display_name": "Classroom A203", "type": "CLASSROOM", "cap": 70, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A204", "floor_id": "floor_A_2", "code": "A204", "display_name": "Classroom A204", "type": "CLASSROOM", "cap": 62, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A205", "floor_id": "floor_A_2", "code": "A205", "display_name": "Classroom A205", "type": "CLASSROOM", "cap": 66, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A206", "floor_id": "floor_A_2", "code": "A206", "display_name": "Classroom A206", "type": "CLASSROOM", "cap": 60, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A207", "floor_id": "floor_A_2", "code": "A207", "display_name": "Classroom A207", "type": "CLASSROOM", "cap": 68, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A208", "floor_id": "floor_A_2", "code": "A208", "display_name": "Classroom A208", "type": "CLASSROOM", "cap": 64, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_ise_lab_1", "floor_id": "floor_A_2", "code": "ISE Lab 1", "display_name": "ISE Lab 1", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "ISE", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_ise_lab_2", "floor_id": "floor_A_2", "code": "ISE Lab 2", "display_name": "ISE Lab 2", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "ISE", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_A2_SPARE", "floor_id": "floor_A_2", "code": "A2-SPARE", "display_name": "Spare A2", "type": "CLASSROOM", "cap": 60, "prov": "ESTIMATED", "alloc": True, "res": False, "is_spare": True, "fac": ["PROJECTOR"]},

        # 3RD FLOOR (3)
        {"id": "room_A301", "floor_id": "floor_A_3", "code": "A301", "display_name": "Classroom A301", "type": "CLASSROOM", "cap": 60, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A302", "floor_id": "floor_A_3", "code": "A302", "display_name": "Classroom A302", "type": "CLASSROOM", "cap": 64, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A303", "floor_id": "floor_A_3", "code": "A303", "display_name": "Classroom A303", "type": "CLASSROOM", "cap": 68, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A304", "floor_id": "floor_A_3", "code": "A304", "display_name": "Classroom A304", "type": "CLASSROOM", "cap": 70, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_cm_lab_1", "floor_id": "floor_A_3", "code": "Civil/Mech Lab 1", "display_name": "Civil/Mech Lab 1", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "MECH_CIVIL", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_cm_lab_2", "floor_id": "floor_A_3", "code": "Civil/Mech Lab 2", "display_name": "Civil/Mech Lab 2", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "MECH_CIVIL", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_cm_lab_3", "floor_id": "floor_A_3", "code": "Civil/Mech Lab 3", "display_name": "Civil/Mech Lab 3", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "MECH_CIVIL", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_A3_SPARE_1", "floor_id": "floor_A_3", "code": "A3-SPARE-1", "display_name": "Spare A3-1", "type": "CLASSROOM", "cap": 60, "prov": "ESTIMATED", "alloc": True, "res": False, "is_spare": True, "fac": ["PROJECTOR"]},
        {"id": "room_A3_SPARE_2", "floor_id": "floor_A_3", "code": "A3-SPARE-2", "display_name": "Spare A3-2", "type": "CLASSROOM", "cap": 64, "prov": "ESTIMATED", "alloc": True, "res": False, "is_spare": True, "fac": ["PROJECTOR"]},
        {"id": "room_A3_SPARE_3", "floor_id": "floor_A_3", "code": "A3-SPARE-3", "display_name": "Spare A3-3", "type": "CLASSROOM", "cap": 66, "prov": "ESTIMATED", "alloc": True, "res": False, "is_spare": True, "fac": ["PROJECTOR"]},

        # 4TH FLOOR (4)
        {"id": "room_A401", "floor_id": "floor_A_4", "code": "A401", "display_name": "Classroom A401", "type": "CLASSROOM", "cap": 60, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A402", "floor_id": "floor_A_4", "code": "A402", "display_name": "Classroom A402", "type": "CLASSROOM", "cap": 62, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A403", "floor_id": "floor_A_4", "code": "A403", "display_name": "Classroom A403", "type": "CLASSROOM", "cap": 65, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A404", "floor_id": "floor_A_4", "code": "A404", "display_name": "Classroom A404", "type": "CLASSROOM", "cap": 68, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A405", "floor_id": "floor_A_4", "code": "A405", "display_name": "Classroom A405", "type": "CLASSROOM", "cap": 70, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_ds_lab_1", "floor_id": "floor_A_4", "code": "DS Lab 1", "display_name": "DS Lab 1", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "DS", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_ds_lab_2", "floor_id": "floor_A_4", "code": "DS Lab 2", "display_name": "DS Lab 2", "type": "LAB", "cap": 35, "prov": "ESTIMATED", "alloc": True, "res": False, "lab_kind": "DS", "fac": ["LAB_EQUIPMENT"]},
        {"id": "room_A4_SPARE_1", "floor_id": "floor_A_4", "code": "A4-SPARE-1", "display_name": "Spare A4-1", "type": "CLASSROOM", "cap": 60, "prov": "ESTIMATED", "alloc": True, "res": False, "is_spare": True, "fac": ["PROJECTOR"]},
        {"id": "room_A4_SPARE_2", "floor_id": "floor_A_4", "code": "A4-SPARE-2", "display_name": "Spare A4-2", "type": "CLASSROOM", "cap": 66, "prov": "ESTIMATED", "alloc": True, "res": False, "is_spare": True, "fac": ["PROJECTOR"]},
        {"id": "room_staff", "floor_id": "floor_A_4", "code": "Staff Room", "display_name": "Staff Room", "type": "STAFF_ROOM", "cap": None, "prov": None, "alloc": False, "res": False, "fac": []},

        # 5TH FLOOR (5)
        {"id": "room_A501", "floor_id": "floor_A_5", "code": "A501", "display_name": "Classroom A501", "type": "CLASSROOM", "cap": 60, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A502", "floor_id": "floor_A_5", "code": "A502", "display_name": "Classroom A502", "type": "CLASSROOM", "cap": 64, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A503", "floor_id": "floor_A_5", "code": "A503", "display_name": "Classroom A503", "type": "CLASSROOM", "cap": 66, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A504", "floor_id": "floor_A_5", "code": "A504", "display_name": "Classroom A504", "type": "CLASSROOM", "cap": 70, "prov": "ESTIMATED", "alloc": True, "res": False, "fac": ["PROJECTOR"]},
        {"id": "room_A5_SPARE_1", "floor_id": "floor_A_5", "code": "A5-SPARE-1", "display_name": "Spare A5-1", "type": "CLASSROOM", "cap": 62, "prov": "ESTIMATED", "alloc": True, "res": False, "is_spare": True, "fac": ["PROJECTOR"]},
        {"id": "room_A5_SPARE_2", "floor_id": "floor_A_5", "code": "A5-SPARE-2", "display_name": "Spare A5-2", "type": "CLASSROOM", "cap": 66, "prov": "ESTIMATED", "alloc": True, "res": False, "is_spare": True, "fac": ["PROJECTOR"]},
        {"id": "room_com_1", "floor_id": "floor_A_5", "code": "Common Room 1", "display_name": "Common Room 1", "type": "COMMON_USE", "cap": None, "prov": None, "alloc": False, "res": False, "fac": []},
        {"id": "room_com_2", "floor_id": "floor_A_5", "code": "Common Room 2", "display_name": "Common Room 2", "type": "COMMON_USE", "cap": None, "prov": None, "alloc": False, "res": False, "fac": []},
    ]

    for r in rooms_data:
        existing = db.query(Room).filter(Room.id == r["id"]).first()
        if not existing:
            room = Room(
                id=r["id"],
                block_id="block_A",
                floor_id=r["floor_id"],
                code=r["code"],
                display_name=r["display_name"],
                resource_type=r["type"],
                capacity=r.get("cap"),
                capacity_provenance=r.get("prov"),
                allocatable_for_classes=r.get("alloc", True),
                reservable_for_events=r.get("res", False),
                lab_kind=r.get("lab_kind"),
                facilities=r.get("fac", []),
                is_spare=r.get("is_spare", False),
                provenance=r.get("prov"),
                accessible=None
            )
            db.add(room)
    
    db.commit()
""",
}

for rel_path, content in files.items():
    full_path = os.path.join(base_dir, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)

print("Files created successfully.")
