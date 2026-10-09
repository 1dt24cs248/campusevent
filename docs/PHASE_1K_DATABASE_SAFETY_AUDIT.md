# Phase 1K Database Safety Audit

## Current Database

Read-only SQLite inspection used `file:.../campus.db?mode=ro` plus `PRAGMA query_only=ON`. The audit executed only SELECT queries and read-only PRAGMAs. No DDL/DML, migration, seed, or repair operation was run. File metadata was unchanged across the audit reads.

| File | Present | Size | Last modified |
|---|---:|---:|---|
| `backend/campus.db` | Yes | 2,027,520 bytes | 2026-10-08 13:58:16.941 +05:30 |
| `backend/campus.db-wal` | Yes | 0 bytes | 2026-10-08 14:00:27.043 +05:30 |
| `backend/campus.db-shm` | Yes | 32,768 bytes | 2026-10-08 14:00:27.043 +05:30 |

- SQLite `user_version`: `0`
- SQLite `journal_mode`: `wal`
- `sqlite_sequence`: absent
- Application tables: 48

## Backup Comparison

The specified archive exists: `C:\Users\Shailendra Kumar N\OneDrive\Desktop\campusevent-after-copilot.zip` (188,602,922 bytes; modified 2026-10-06 07:14:47 +05:30).

The ZIP contains:

| Member | ZIP-reported size | ZIP-reported member time |
|---|---:|---|
| `campusevent-backup-temp/backend/campus.db` | 1,298,432 bytes | 2026-10-05 21:35:36 |
| `campusevent-backup-temp/backend/campus.db-wal` | 4,124,152 bytes | 2026-10-06 00:14:52 |
| `campusevent-backup-temp/backend/campus.db-shm` | 32,768 bytes | 2026-10-05 20:56:02 |

Only the archived `campus.db` member was extracted, to `C:\Users\Shailendra Kumar N\.copilot\session-state\f43de5b7-0c01-4197-8009-afbaa22c23d2\files\phase1k-db-audit\campus.db`. Nothing was extracted over the project.

The archived main database and current database both report `user_version=0` and `journal_mode=wal`. **The comparison is against the extracted archived main DB only.** Its archived WAL is 4,124,152 bytes, with a valid-looking SQLite WAL header and 1,001 frames by file size. It was not extracted or applied, as requested. Consequently, the extracted main DB may omit committed changes present in the archived WAL; it is not safe to call it a complete effective backup snapshot.

At the main-file level, the current database has 48 tables and the extracted backup main DB has 37. There are no backup-only table names. The current-only tables and their row counts are:

| Current-only table | Current rows | Backup main DB |
|---|---:|---:|
| `academic_marks` | 0 | absent |
| `academic_resources` | 0 | absent |
| `attendance_records` | 0 | absent |
| `attendance_sessions` | 2 | absent |
| `classroom_requests` | 0 | absent |
| `emergency_contacts` | 0 | absent |
| `food_locations` | 0 | absent |
| `food_menu_items` | 0 | absent |
| `food_menus` | 0 | absent |
| `report_histories` | 3 | absent |
| `syllabus_modules` | 0 | absent |

Main-file row-count comparison (the backup column is the extracted main DB, not its unapplied WAL):

| Table | Current | Backup main DB | Difference |
|---|---:|---:|---:|
| `academic_marks` | 0 | absent | new table, empty |
| `academic_resources` | 0 | absent | new table, empty |
| `announcements` | 0 | 0 | 0 |
| `approvals` | 16 | 7 | +9 |
| `assessments` | 0 | 0 | 0 |
| `attendance_records` | 0 | absent | new table, empty |
| `attendance_sessions` | 2 | absent | new table, 2 rows |
| `audit_logs` | 272 | 140 | +132 |
| `blocks` | 1 | 1 | 0 |
| `campus_faqs` | 0 | 0 | 0 |
| `classroom_requests` | 0 | absent | new table, empty |
| `departments` | 7 | 7 | 0 |
| `emergency_configs` | 0 | 0 | 0 |
| `emergency_contacts` | 0 | absent | new table, empty |
| `emergency_events` | 1 | 0 | +1 |
| `event_rooms` | 0 | 0 | 0 |
| `events` | 0 | 0 | 0 |
| `faculties` | 58 | 58 | 0 |
| `floors` | 7 | 7 | 0 |
| `food_locations` | 0 | absent | new table, empty |
| `food_menu_items` | 0 | absent | new table, empty |
| `food_menus` | 0 | absent | new table, empty |
| `incident_status_histories` | 0 | 0 | 0 |
| `incidents` | 1 | 0 | +1 |
| `maintenance_tickets` | 1 | 0 | +1 |
| `nav_configs` | 0 | 0 | 0 |
| `nav_edges` | 0 | 0 | 0 |
| `nav_nodes` | 1 | 0 | +1 |
| `notification_reads` | 0 | 0 | 0 |
| `notifications` | 138 | 63 | +75 |
| `opportunities` | 0 | 0 | 0 |
| `optimization_runs` | 116 | 72 | +44 |
| `published_versions` | 16 | 7 | +9 |
| `report_histories` | 3 | absent | new table, 3 rows |
| `room_unavailability` | 0 | 0 | 0 |
| `rooms` | 62 | 62 | 0 |
| `scenario_changes` | 79 | 48 | +31 |
| `scenarios` | 79 | 48 | +31 rows and 1 shared row differs |
| `section_strength_histories` | 0 | 0 | 0 |
| `sections` | 27 | 27 | 0 |
| `session_overrides` | 235 | 91 | +144 |
| `settings` | 0 | 0 | 0 |
| `students` | 3 | 3 | 0 |
| `subjects` | 36 | 36 | 0 |
| `syllabus_modules` | 0 | absent | new table, empty |
| `ticket_histories` | 0 | 0 | 0 |
| `timetable_entries` | 559 | 559 | 0 |
| `users` | 9 | 9 | 0 |

For tables present in both main files, row comparison on their shared columns found added rows in `approvals`, `audit_logs`, `emergency_events`, `incidents`, `maintenance_tickets`, `nav_nodes`, `notifications`, `optimization_runs`, `published_versions`, `scenario_changes`, `scenarios`, and `session_overrides`. No shared primary-key row was removed. One shared `scenarios` row differs. The exact counts are reflected in the table above. This proves differences between the two inspected main-file images, not when or why they occurred.

Important application records by count:

- Published versions: 16 current versus 7 in the backup main DB.
- Scenarios: 79 versus 48; scenario changes: 79 versus 48.
- Overrides: 235 versus 91.
- Notifications: 138 versus 63.
- Students: 3 versus 3; faculty: 58 versus 58.
- Rooms: 62 versus 62; floors: 7 versus 7.
- Timetable entries: 559 versus 559.
- Food locations, menus, and menu items: 0 current; those tables are absent from the backup main DB.
- Academic marks/resources: 0 current; academic marks/resources tables are absent from the backup main DB.

Equal counts do not prove every column or all WAL state is equal. For common existing columns, the compared main-file rows for students, faculty, rooms, floors, and timetable entries matched; some current columns did not exist in the backup schema and therefore cannot be compared.

## Schema Differences

The extracted backup main DB has 37 application tables; current has 48. Current has no backup-only tables. Relative to the extracted backup main-file image:

1. **11 tables are present only in current:** `academic_marks`, `academic_resources`, `attendance_records`, `attendance_sessions`, `classroom_requests`, `emergency_contacts`, `food_locations`, `food_menu_items`, `food_menus`, `report_histories`, and `syllabus_modules`.
2. **Nine shared table definitions have additional columns in current:**
   - `announcements`: `section_id`
   - `assessments`: `description`, `maximum_marks`, `created_by`, `status`, `created_at`, `updated_at`, `is_synthetic`, `provenance`
   - `emergency_events`: `code`, `category`, `description_enc`, `room_id`, `severity`, `priority`, `assigned_to`, `updated_at`, `resolved_at`, `resolution_note`
   - `events`: `location`, `organizer`, `created_by`, `created_at`, `updated_at`, `decision_reason`, `decided_by`, `decided_at`, `notes`
   - `faculties`: `employee_id`, `designation`
   - `incidents`: `anonymous`, `location_room_id`, `severity`, `priority`, `assigned_to`, `updated_at`, `resolved_at`, `resolution_note`
   - `maintenance_tickets`: `report_type`, `location_text`, `updated_at`, `resolved_at`, `resolution_note`
   - `students`: `usn`, `phone`, `program`, `semester`, `admission_year`, `academic_status`, `profile`
   - `subjects`: `description`, `credits`
3. Four additional unique indexes are present in current:
   - `uq_faculties_employee_id` on `faculties(employee_id)`
   - `uq_faculties_user_id` on `faculties(user_id)`
   - `uq_students_user_id` on `students(user_id)`
   - `uq_students_usn` on `students(usn)`
4. The new-table schema also has these 17 additional non-unique indexes:
   - `ix_academic_marks_assessment_id`, `ix_academic_marks_student_id`
   - `ix_academic_resources_section_id`, `ix_academic_resources_subject_id`
   - `ix_attendance_records_session_id`, `ix_attendance_records_student_id`
   - `ix_attendance_sessions_faculty_id`
   - `ix_classroom_requests_faculty_id`, `ix_classroom_requests_requested_date`, `ix_classroom_requests_status`
   - `ix_emergency_contacts_user_id`
   - `ix_food_menu_items_menu_date`
   - `ix_food_menus_location_id`, `ix_food_menus_menu_date`, `ix_food_menus_status`
   - `ix_report_histories_report_id`
   - `ix_syllabus_modules_subject_id`

No other shared `sqlite_master` SQL definition differences or foreign-key-list differences were found in the main-file comparison. Since the archived WAL was not applied, these findings are not a complete comparison of the effective backup database.

## Data Differences

**Application-row differences are present** between the current main DB and extracted backup main DB. In particular, current has more approvals, audit entries, notifications, optimization runs, published versions, scenarios, scenario changes, and overrides, plus one each of emergency event, incident, maintenance ticket, and navigation node. It also has two attendance-session rows and three report-history rows in tables absent from the backup main DB.

This is not a timestamp-only inference; it is based on row counts and primary-key/shared-column comparisons. However, the ZIP backup predates the current database and includes an unapplied 1,001-frame WAL. The comparison does **not** establish which differences were already in that WAL, which rows were written between archive creation and the audit, or whether any specific change came from the pytest commands.

## What Is Proven

- The audited current database reports 48 tables, `user_version=0`, WAL journal mode, and no `sqlite_sequence`.
- The ZIP contains a `campus.db`, `campus.db-wal`, and `campus.db-shm`.
- The current main-file image differs from the extracted backup main-file image in schema and application rows, as detailed above.
- The current database’s file and sidecar metadata did not change during this read-only audit.
- The earlier Phase 1K test commands were run without `DATABASE_URL=sqlite://`. `Settings` defaults to `sqlite:///./campus.db`; `backend/app/db.py` builds the engine from that setting, and `backend/app/main.py` runs `Base.metadata.create_all()` plus schema migrations at module import.
- Test modules import `app.main` before installing their per-test `get_db` overrides. Those overrides send test requests to in-memory SQLite fixtures, but they do not prevent the module-import `create_all`/migration calls from using the default engine.
- The specific earlier pytest runs were not isolated from that import-time schema setup. The files contain application rows that differ from the ZIP’s main-file image.
- During this audit, neither current database nor its sidecars were intentionally written. No tests, migrations, server, or application code were run.

## What Cannot Be Proven

- There is no captured, byte-for-byte pre-test copy or pre-test schema/row manifest for `campus.db`; therefore the exact before/after effect of those pytest runs cannot be attributed.
- The backup ZIP’s WAL was deliberately not extracted/applied. The extracted main DB alone may not represent the backup’s effective committed state, so the comparison cannot certify the full backup’s row counts or exact schema.
- The present schema differences versus the backup main DB cannot be assigned specifically to the Phase 1K pytest imports; they may predate those runs.
- Application-row differences versus the older backup cannot be attributed to pytest or any other single activity. Application startup code shown here performs table creation/migrations, not an application data seed, but that does not establish the origin of the currently differing rows.
- No recovery, rollback, or repair conclusion can be drawn safely from this comparison.

## Risk Assessment

**High / unresolved.** The current database differs from the supplied backup main-file image in both schema and application data. The archived backup also has a substantial unapplied WAL, so it is not a clean standalone baseline for complete comparison. The earlier test process used an unsafe default database configuration for import-time schema setup. The evidence does not prove that pytest changed application rows, nor does it prove that it did not. Do not use the production database for further tests, migrations, seed operations, or feature work until the owner has reviewed the differences and the backup is compared as a coherent SQLite snapshot.

## Recommendation

DO NOT CONTINUE

Do not load final A-Block data or run additional migrations/tests against `campus.db`. First have the database owner or DBA validate the current DB and a WAL-consistent backup snapshot, preserve appropriate copies under an approved process, and decide how to handle the schema and application-row differences. No production-database repair was attempted. Final A-Block data has NOT been loaded.
