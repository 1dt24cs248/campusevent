"""Campus Intelligence & Action Platform - FastAPI Application."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, campus
from app.routers import timetable as timetable_router
from app.routers import scenarios as scenarios_router
from app.routers import ai as ai_router
from app.routers import nav as nav_router
from app.routers import actions as actions_router
from app.routers import management as management_router
from app.routers import student as student_router
from app.routers import faculty as faculty_router
from app.routers import events as events_router
from app.routers import food as food_router
from app.db import Base, engine
from app.action_schema import migrate_action_columns
from app.identity_schema import migrate_identity_columns
from app.event_schema import migrate_event_columns
from app.food_schema import migrate_food_schema
from app.academic_schema import migrate_academic_schema
from app.config import settings

# Create all tables on startup (seed script also does this)
Base.metadata.create_all(bind=engine)
migrate_action_columns(engine)
migrate_identity_columns(engine)
migrate_event_columns(engine)
migrate_food_schema(engine)
migrate_academic_schema(engine)
if (
    not settings.APP_ENCRYPTION_KEY
    or settings.APP_ENCRYPTION_KEY == "change-me"
    or settings.JWT_SECRET == "change-me"
):
    logging.getLogger(__name__).warning(
        "Report encryption is using a missing or default secret. Run app.seed.gen_keys and "
        "configure a dedicated APP_ENCRYPTION_KEY before using confidential reports."
    )

app = FastAPI(
    title="Campus Intelligence & Action Platform",
    description="AI-Powered What-If Decision Simulator for Smart Campus Management - Block A Pilot",
    version="0.2.0",
)

# CORS: limit to frontend dev server per spec
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(campus.router, prefix="/api", tags=["campus"])
app.include_router(timetable_router.router, prefix="/api", tags=["timetable"])
app.include_router(scenarios_router.router, prefix="/api", tags=["scenarios"])
app.include_router(ai_router.router, prefix="/api", tags=["ai"])
app.include_router(nav_router.router, prefix="/api", tags=["navigation"])
app.include_router(actions_router.router, prefix="/api", tags=["campus actions"])
app.include_router(management_router.router, prefix="/api", tags=["management"])
app.include_router(student_router.router, prefix="/api", tags=["student"])
app.include_router(faculty_router.router, prefix="/api", tags=["faculty"])
app.include_router(events_router.router, prefix="/api", tags=["events"])
app.include_router(food_router.router, prefix="/api", tags=["food"])


@app.get("/health")
def health_check():
    return {"status": "ok", "app": "Campus Intelligence & Action Platform"}
