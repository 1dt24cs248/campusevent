# Phase 1K Final Verification

## Environment Safety
- Database used: `backend/phase1j-e2e.sqlite` was inspected through SQLite read-only mode for the persisted stress result and version/override/notification state. Final automated test reruns used `DATABASE_URL=sqlite://` (in-memory).
- Backend port: 8766 for the earlier explicit isolated runtime verification; no backend server was started in this report pass.
- Frontend port: 5182 for the earlier browser verification; no frontend server was started in this report pass.
- Production database touched? YES — the initial pytest runs in this pass did not set `DATABASE_URL`. Importing `app.main` runs `Base.metadata.create_all` and schema migrations using the configured engine, whose default is `sqlite:///./campus.db`. The `backend/campus.db` and SQLite sidecar timestamps advanced during that period. No scenario/publish/revert API calls or data seeding were directed at that file, and the precise schema/data impact was not established. Subsequent test reruns explicitly used `sqlite://`. Do not treat the production database as certified untouched until it has been audited.
- Port 8000: no requests were made to it during this report pass. A prior browser interaction in the preceding verification used a Vite process with its default `localhost:8000` API proxy for authentication/read-only requests; its backend database target was not established.
- test_api.py run? NO.
- Final A-Block data has NOT been loaded.

## 1G Food
PARTIAL

The broader regression command included `test_food.py` and `test_actions.py` and passed. Existing runtime evidence reports no food stalls or menus in the isolated validation database, so published food visibility, real stall/menu lifecycle, and role behavior were not demonstrated end-to-end in this pass. No food data was created.

## 1H Academic ERP
PARTIAL

Academic/student/faculty regression files were included in the passing backend suite. The Management Academic page was previously observed displaying the validation section and subject labels. This pass did not repeat student/faculty academic browser workflows or verify a full real academic dataset.

## 1I Management ERP
PARTIAL

Management regression coverage passed, and Management Academic provenance labels were observed in the prior isolated browser run. The full management portal workflows were not repeated end-to-end in this pass.

## 1J What-If
### ROOM_UNAVAILABLE
PASS — The prior isolated runtime verification simulated V101 closure and produced a meaningful CSE101 / 3CSE-A decision row with V101 → V201, `REASSIGNED`.

### FLOOR_UNAVAILABLE
PASS — The prior isolated runtime verification selected recorded `floor_validation_1` and simulated its closure. One class was affected and reassigned from V101 to V201.

### STRESS_TEST
PASS — Read-only inspection of `phase1j-e2e.sqlite` confirmed scenario `scen_a580c35bee`, run `run_054b92d0ff`, remains `STRESS_TEST` / `PARTIAL`, with payload `{"k":"5"}`. Persisted metrics and assignments still match the prior result:
- affected: 2
- reassigned: 1
- unchanged: 0
- unresolved: 1
- conflicts: 0 → 0
- utilization ratio: 0.8 → 0.8571
- capacity pressure: 0 → 1
- walking effort: 3
- wasted capacity: 10

The persisted run assigns `entry_nonprojector_validation` to `room_noproj_valid` (V102) and records `entry_projector_validation` as unresolved. The stress condition records two occupied rooms selected: V101 and V201.

### Review / Approval / Publish
PASS — Prior isolated runtime evidence recorded review and successful publication of Version 2, with one override and two ROOM_CHANGED notifications.

### Stale Version
PASS — Prior isolated runtime attempt to publish a stale scenario returned HTTP 409 with detail `Stale version: campus state has changed since scenario creation`.

### Revert
PASS — Prior isolated runtime revert returned HTTP 200 with `{"ok":true,"reverted_overrides":1}`. Version 2's override is inactive and the class was observed returning to V101.

### Notifications
PARTIAL — `test_room_unavailable_publish_revert_notifications_and_rbac` now verifies affected student/faculty notification delivery and excludes unrelated student/faculty accounts for both ROOM_CHANGED and newly created VERSION_REVERTED notices; the focused test passes. The existing isolated database still contains one historical VERSION_REVERTED notification with audience `ROLE` / `ALL` from the earlier implementation. It was not rewritten or removed, so unrelated users querying that persistent database could still receive that old notice.

The code fix scopes new revert notices to each affected section and faculty. The legacy persistent notice remains a cleanup/verification gap.

### Overrides
PASS — Read-only inspection confirmed Version 2 (`ver_83ca15cf36`) is marked reverted and its V101 → V201 override is inactive. Version 3 (`ver_87efc19a70`) remains published and not reverted, with its own active override for `entry_nonprojector_validation`. No publish/revert workflow was rerun in this pass.

## Navigator
PARTIAL

The implementation is data-driven: the room directory, floors, blocks, and route nodes are loaded from APIs. Focused tests pass for room-code and room-ID lookup, floor filtering, block/floor/type details, unknown floors, Basement label, graph routing, and the honest no-route state. The UI renders location identity, block, floor, type, and capacity when present; it makes no GPS or walking-distance claim. No hardcoded A101/A102/V101/V201 list was found in `NavPanel`.

NOT VERIFIED — isolated runtime dataset contains no Basement records. The focused in-memory Navigator fixture includes a level -1 lab and verifies the returned floor is `Basement`; the current `phase1j-e2e.sqlite` has only its validation floors, so Basement was not verified in a browser against the persisted runtime dataset.

## AI
NOT VERIFIED

AI workflows were not exercised in this final pass. Earlier evidence is not treated as a fresh verification here.

## Provenance
PARTIAL

The isolated browser previously showed “Synthetic / Validation” for the synthetic section and subject. The frontend helper tests pass for explicit synthetic flags and synthetic/validation provenance, and confirm that `OWNER_SUPPLIED`, `CURATED_CAMPUS_DATA`, `NOT_SYNTHETIC`, and missing provenance are not labeled synthetic.

The helper only classifies records; it does not assign or invent provenance. Room schemas expose `provenance` and `capacity_provenance`, and timetable response schemas expose `provenance`. However, the current management academic response does not expose subject provenance, and the application/tests contain no `REAL_TIMETABLE_PDF` fixture or value. `ESTIMATED` occurs in the dormant Block A seed source but was not loaded or exercised in this pass. Distinguishability of those two provenance values in actual API/UI records is therefore NOT VERIFIED.

## Automated Tests
- Focused backend, run from the `backend` directory: `$env:DATABASE_URL='sqlite://'; & 'C:\Users\Shailendra Kumar N\OneDrive\Desktop\campusevent\backend\.venv\Scripts\python.exe' -m pytest -q test_scenario_lifecycle.py test_nav.py` — **6 passed, 0 failed**, 9 deprecation warnings.
- Broader backend regression, run from the `backend` directory and excluding `test_api.py`: `$env:DATABASE_URL='sqlite://'; & 'C:\Users\Shailendra Kumar N\OneDrive\Desktop\campusevent\backend\.venv\Scripts\python.exe' -m pytest -q test_management.py test_student_portal.py test_faculty_portal.py test_identity.py test_academics.py test_events.py test_food.py test_actions.py test_phase1j_focused.py test_nav.py` — **73 passed, 0 failed**, 9 deprecation warnings.
- Frontend helper tests: `node --test tests/academicRecordProvenance.test.ts tests/navLocation.test.ts` — **5 passed, 0 failed**.
- `test_api.py` was not run.

The test reruns after identifying the database configuration risk explicitly used an in-memory app-startup database. The first pytest runs did not; see Environment Safety.

## Frontend Build
PASS — `npm run build` succeeded (`tsc -b` and Vite production build). Vite emitted a large-chunk advisory for the approximately 978 kB JavaScript bundle; this was a warning, not a build failure.

## Frontend Lint
PASS — `npm run lint` exited successfully. Oxlint reported one existing Fast Refresh warning in `src/context/AuthContext.tsx`; this was a warning, not a lint failure.

## Remaining Gaps
- Audit `backend/campus.db` before further use. Initial test processes imported app startup with the default database URL; timestamps advanced, and the exact schema/data impact has not been established.
- The old global VERSION_REVERTED notice remains in the isolated database. New reverts are scoped by code and covered by the focused test, but the legacy notice remains visible to all roles.
- Basement was covered by an in-memory API fixture, not by the persisted runtime database/browser.
- `REAL_TIMETABLE_PDF` and `ESTIMATED` provenance were not verified through actual records and UI; subject provenance is not returned by the management academic endpoint.
- Food, complete student/faculty/management ERP browser workflows, and role-aware AI were not fully exercised in this final pass.

## Competition Readiness
NOT READY

Do not proceed to final A-Block data population until the `campus.db` startup side effect has been audited and the persistent legacy global VERSION_REVERTED notice/provenance verification gaps have been addressed or explicitly accepted. Final A-Block data has NOT been loaded.

Verification tally for this report: **16 PASS**, **2 FAIL**, **7 NOT VERIFIED**. The failures are the initial test startup targeting the default campus database and the legacy global VERSION_REVERTED notification still present in the isolated database; they are distinct from the automated test failure count, which is zero.
