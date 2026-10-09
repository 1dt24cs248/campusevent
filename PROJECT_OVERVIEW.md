# Campus Intelligence & Action Platform

**Project overview and current demo reference**  
Snapshot reviewed: 9 October 2026  
Pilot scope: Block A campus operations

## 1. Purpose

This project is a role-based campus operations platform with a management What-If simulator. Management can model a room closure or other supported change, inspect affected classes, compare optimizer proposals, and publish only after approval. Students and faculty then read timetable data scoped to their own section or faculty profile.

The optimizer, not the AI assistant, decides room allocation. Simulation is an in-memory proposal; it does not become the published timetable until management approves it. The project is a local proof of concept, not a production ERP, room-booking service, or fully populated campus timetable.

## 2. Architecture and design

The frontend is React 19 and TypeScript, built with Vite. It uses React Router for role-protected pages, TanStack Query for API data, Axios for HTTP requests, Tailwind CSS 4 for styling, and Lucide icons. The current interface is a dark slate operations dashboard with indigo and cyan accents.

The backend is FastAPI with SQLAlchemy models and Pydantic schemas. REST endpoints are mounted below `/api`; Uvicorn serves the application. The application uses SQLite for the local demo and accepts another SQLAlchemy-compatible database URL through `DATABASE_URL`.

The allocation engine uses OR-Tools CP-SAT. It filters rooms by type, known capacity, facilities, availability, and time-slot occupancy. Unknown capacity is treated as insufficient rather than guessed. Network/route data is represented by navigation nodes and edges; without edges, a room can be listed without a turn-by-turn route.

Authentication uses bcrypt password hashes and bearer JWTs with an eight-hour lifetime. The frontend keeps its token in local storage. Authorization is role-based, with profile and ownership checks for student and faculty data. The default AI mode is rule-based (`LLM_PROVIDER=none`); optional LLM providers can be configured, but they do not control room assignment.

## 3. Main workflows

### Sign-in and role routing

The client sends credentials to `POST /api/auth/login`, stores the returned token, then loads `GET /api/auth/me`. Protected frontend routes are selected by role: Management, Faculty, Student, and other supported roles. A student's timetable is resolved through the linked student profile and section; faculty assignments are resolved through the linked faculty profile and timetable rows.

### Management What-If workflow

1. Create a scenario or choose a preset.
2. Simulate changes against a temporary state snapshot.
3. Review impact, optimizer options, moved classes, capacity, and unresolved placements.
4. Compare or revise options, then review the selected result.
5. Approve and publish to create a version, dated session overrides, notifications, and audit records.
6. Revert a published version when needed; its overrides are deactivated.

Supported scenario families include room/floor unavailability, room reservations, strength changes, adding a section, moving a class, and stress tests. A scenario that lacks valid rooms remains partial or unresolved rather than being presented as feasible.

### Student and faculty workflows

Students have a dashboard, profile, section timetable, academic pages, events, notifications, campus navigation, AI assistant, and reporting/emergency flows. Faculty have a dashboard, timetable, assigned subjects and sections, attendance, academic content management, classroom requests, events, notifications, and reporting flows. Management has campus overview, academic directory, identity management, scenario/version workflows, requests, events, food management, and audit views.

Academic content is not seeded merely to fill the interface. At this snapshot, assessments, resources, marks, and attendance records are empty; a faculty or management workflow must create and publish records before students see them.

## 4. Supplied datasets and how they relate to the demo

The workspace includes the following input files:

- [`data/blockA_master.json`](data/blockA_master.json) describes Block A, seven floor labels, seven departments, and twelve explicit room objects (eight basement and four ground-floor records). The final competition database has 61 room/location records because it was assembled by a separate population script; the final room table is not a literal import of this JSON file.
- [`data/sections.json`](data/sections.json) contains 27 legacy section codes and strengths. The competition population script creates 29 normalized, non-synthetic sections directly; the academic continuation then adds synthetic CSE 1A and CSE 1B, making 31 in the current database. The older codes are not copied verbatim into the final database.
- [`data/timetable_template.csv`](data/timetable_template.csv) contains ten synthetic weekly rows for the legacy section name `3CSE-A`. It is a sample/legacy template, not the schedule currently stored in `campus_demo.db`.
- [`data/FFINAL-5th  SEM CSE TT.pdf`](data/FFINAL-5th%20%20SEM%20CSE%20TT.pdf) is a six-page fifth-semester CSE timetable. The reliable 5A and 5B theory rows are represented as 17 entries each for CSE 3A and CSE 3B. The imported PDF rows preserve timetable, subject, section, and faculty provenance.
- [`PROJECT_SPEC.txt.txt`](PROJECT_SPEC.txt.txt) describes the intended product, constraints, and initial master data. It is a requirements source, not a guarantee that every specified dataset or feature is loaded in the current demo.
- [`setup.txt`](setup.txt) is an older installation/demo guide. Some commands, account names, and data assumptions in it are stale relative to the current competition database.

The isolated competition dataset was created by [`backend/populate_competition_data.py`](backend/populate_competition_data.py) and extended by [`backend/continue_demo_academics.py`](backend/continue_demo_academics.py). The continuation records PDF room mappings and unresolved rows in the `settings` table with `competition_*` keys.

### Current loaded data snapshot

These figures are from the current `backend/data/campus_demo.db`, not from the older source files or validation database:

- 1 Block A, 7 floors, 61 rooms/locations, and 8 departments.
- 31 sections: 29 non-synthetic sections and synthetic CSE 1A / CSE 1B.
- 65 student profiles in the database. The original competition population reported 64 CSE 3A identities (seven owner-provided names and 57 synthetic placeholders); the additional Demo Student account is also linked to CSE 3A.
- 16 faculty profiles: 15 populated faculty plus the Demo Faculty profile.
- 127 subjects. The population report describes 115 synthetic curriculum subjects plus owner-provided and PDF-linked subjects.
- 44 actual timetable entries: 34 `REAL_TIMETABLE_PDF` rows and 10 `SYNTHETIC` first-year theory rows.

The population report says only two room capacities are explicitly known: SH01 is 90 and SH02 is 75; 59 room capacities are `NULL`. Those halls are designated for first-year CSE/seminar use. CSE 3A has 17 PDF-derived rows with no base room because the PDF's room 202 maps to candidate A202, which is an ISE room with unknown exact capacity. No substitute room was guessed. Other planned synthetic periods/labs remain unresolved rather than becoming timetable entries.

## 5. Database design

SQLAlchemy models are grouped under `backend/app/models/`:

- Campus: `Block`, `Floor`, `Room`, navigation nodes, and edges.
- Academic identity: `Department`, `Section`, `Subject`, `Faculty`, and `Student`.
- Schedule: `TimetableEntry`, `SessionOverride`, and section-strength history.
- Simulation: `Scenario`, `ScenarioChange`, `OptimizationRun`, `Approval`, and `PublishedVersion`.
- Workflow: notifications and notification-read state.
- Operations: events, classroom requests, maintenance, food, announcements, opportunities, attendance, assessments, and learning resources.
- Safety and access: users, encrypted incident-related records, emergency records, and audit logs.
- Configuration/provenance: `settings` stores JSON configuration and competition review data; sourceable records carry provenance fields.

A timetable entry is a weekly record with a nullable `base_room_id`. A dated, active `SessionOverride` supplies a different effective room for the specified date. Scenario simulation overlays changes in memory; publishing persists approved changes and a version. Student and faculty timetable endpoints resolve only entries associated with the authenticated user's profile.

## 6. Verified demo credentials

These three current accounts were verified against the password hashes in `campus_demo.db`. They are for local demo use only.

- Management: `manager@demo.local` / `Demo@1234`
- Student: `student@demo.local` / `Demo@1234` (Demo Student, CSE 3A)
- Faculty: `faculty@demo.local` / `Demo@1234` (Faculty Engineering-01)

The current Faculty Engineering-01 account owns the existing CSE 1A and CSE 1B synthetic timetable entries. The former Demo Faculty profile is linked to a deactivated account at `demo-faculty-disabled@demo.local` and has no timetable assignments. It cannot be used to sign in.

Other populated student/faculty records have password hashes, not recoverable plaintext passwords. The older setup guide's `management@demo.local` address is not the verified management account for this database. Do not use these demo credentials in a deployed or shared environment.

## 7. Starting the correct demo

The normal `scripts/start_backend.bat` launcher starts port 8000 and defaults to `campus.db`. For the competition demo, explicitly select the populated database and the port used by the frontend proxy.

From the repository root, start the backend in one PowerShell terminal:

```powershell
cd backend
$env:DATABASE_URL = "sqlite:///./data/campus_demo.db"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8766
```

In a second terminal, start the frontend:

```powershell
cd frontend
npm run dev
```

Vite proxies `/api` to `http://localhost:8766` by default. The app is usually available at `http://localhost:5173`. Backend startup runs `create_all` and schema migrations, so set `DATABASE_URL` before launching it. Never run tests with `DATABASE_URL` pointing to a protected database; use `sqlite://` for in-memory pytest runs.

## 8. Current published state and known gaps

The latest version in the current demo database is version 3, “SH01 Emergency Closure,” marked published and not reverted. It contains five active date-specific overrides moving CSE 1A classes from SH01 to SH02. Version 2 also remains unreverted with five active overrides for the same entries; version 1 is reverted and its five overrides are inactive. The latest change does not affect CSE 3A.

Important data and readiness limits:

- All 34 PDF timetable entries have no assigned base room; the source room mappings are explicitly unresolved.
- 59 room capacities are unknown. Do not assign a room based on an unverified capacity range.
- Assessments, academic resources, marks, attendance records, announcements, opportunities, food menus, maintenance tickets, incidents, emergency events, and classroom requests currently have no records. One attendance session and one event record exist.
- Navigation has 61 room nodes but zero route edges, so turn-by-turn navigation is not mapped.
- The database contains 13 scenarios, three published versions, 15 override records, and 12 notification records. Two published versions currently have active overrides for the same first-year CSE entries.
- `BUILD_STATUS.md` still reports M1 and is stale. The dated Phase 1K report records 73 backend tests passing, five frontend helper tests passing, and frontend build/lint passing; `test_api.py` was not run. Its browser evidence used `phase1j-e2e.sqlite`, not the current competition database.
- The Phase 1K report records that earlier test startup advanced `campus.db` metadata and that the exact impact was not established. Do not describe that database as certified untouched based on the available reports.

The dated verification report marks overall competition readiness **NOT READY**. The core simulator workflows have meaningful test evidence, but the populated competition database, full browser workflows, unknown room capacities, unresolved PDF rooms, and navigation data still have verification or data gaps.

## 9. Verification sources

This overview is based on the current repository files and a read-only inspection of `backend/data/campus_demo.db`, plus:

- [`docs/FINAL_A_BLOCK_DATA_POPULATION_REPORT.md`](docs/FINAL_A_BLOCK_DATA_POPULATION_REPORT.md)
- [`docs/PHASE_1K_FINAL_VERIFICATION.md`](docs/PHASE_1K_FINAL_VERIFICATION.md)
- [`docs/FINAL_DEMO_EVIDENCE.md`](docs/FINAL_DEMO_EVIDENCE.md)
- [`backend/app/main.py`](backend/app/main.py)
- [`backend/app/routers/`](backend/app/routers/)
- [`frontend/src/App.tsx`](frontend/src/App.tsx)

The database totals above are current to the snapshot reviewed on 9 October 2026; scenario, notification, and operational data may change as the demo is used.
