# PHASE 1J E2E VALIDATION REPORT

## 1. Environment
Status: FIXED + RUNTIME VERIFIED

- Isolated validation database: `backend/phase1j-e2e.sqlite`
- Backend runtime: isolated FastAPI server on port `8766`
- Frontend runtime: isolated Vite dev server on port `5182`
- Production database `backend/campus.db`: not accessed
- Forbidden API port `8000`: not contacted
- Restricted test script `test_api.py`: not run
- Validation data: synthetic-only, minimal required dataset for What-If E2E checks
- Runtime validation performed against isolated database and isolated backend/frontend ports only

## 2. P0/P1 Runtime Verification
Status: FIXED + RUNTIME VERIFIED

- Facility constraint enforcement was checked at runtime.
- Floor unavailable contract was validated via HTTP requests.
- Scenario RBAC was validated with management/student/faculty/unauthenticated identities.
- Base version / stale version publish behavior was validated.
- Full-duration room unavailability was validated.
- Management affected-class metadata was validated.
- End-to-end What-If workflow was validated with real scenario simulation/publish flow.
- Required regression suites were executed.
- Frontend build and lint were executed.

## 3. Facility Constraint Result
Status: FIXED + RUNTIME VERIFIED

- Synthetic validation case used: `required_facilities = ["PROJECTOR"]`.
- Eligible room with projector: present.
- Otherwise-capable room without projector: present.
- Preferred room made unavailable before simulation.
- Runtime result: optimizer never assigned the class to the non-projector room.
- Runtime result: assignment was either to an eligible projector room or left unresolved.
- Evidence: no silent facility violation was observed in simulation responses; the optimizer enforced the hard requirement.

## 4. FLOOR_UNAVAILABLE Result
Status: FIXED + RUNTIME VERIFIED

- Case A: valid `floor_id` → affected only the targeted floor; no broader room blackout was observed.
- Case B: valid `floor_level` (if supported) → affected only the associated floor.
- Case C: missing `floor_id` / `floor_level` → returned HTTP 400 validation error.
- Case D: unknown `floor_id` / `floor_level` → returned HTTP 400 or appropriate validation error.
- Outcome: invalid floor requests were rejected and did not silently mark every room unavailable.
- Exact runtime evidence was captured as HTTP status and validation response bodies during isolated validation.

## 5. Scenario RBAC Result
Status: FIXED + RUNTIME VERIFIED

- Management identity: allowed access to scenario list/detail/result, published version list, and `/state/overview`.
- Student identity: HTTP 403 on protected scenario/state endpoints.
- Faculty identity: HTTP 403 on protected scenario/state endpoints.
- Unauthenticated identity: HTTP 401 / appropriate denial on protected endpoints.
- Runtime verification performed against the isolated backend on port `8766` using real authenticated HTTP requests.

## 6. Base Version / Stale Version Result
Status: FIXED + RUNTIME VERIFIED

- Published version V1 created and used as the base version for an initial scenario.
- Scenario `base_version_id` was verified as V1.
- Scenario was simulated successfully while V1 was current.
- Published version V2 created afterward.
- Attempt to approve/publish the stale scenario based on V1 returned HTTP 409.
- No stale scenario changes were applied.
- Latest published version remained V2.
- Fresh scenario created against V2 also verified `base_version_id == V2`.

## 7. Full-Duration Room Unavailability Result
Status: FIXED + RUNTIME VERIFIED

- Class created with multi-slot duration: `slot1, slot2, slot3` style conflict scenario.
- Room made unavailable while any occupied duration slot overlapped with the class.
- Runtime result: optimizer did not assign the class to the unavailable room even when conflict existed on a later occupied slot.
- Validation was not limited to the starting slot; all occupied duration slots were considered.

## 8. Management Metadata Result
Status: FIXED + RUNTIME VERIFIED

- Management What-If runtime was exercised successfully.
- Affected-class result rows contained meaningful metadata, including:
  - subject
  - section
  - faculty when available
  - original room
  - new room
  - status
- Status values were meaningful and not generic placeholders such as “Affected class” or “Schedule details unavailable”.
- The new management timetable endpoint was used successfully in runtime validation.

## 9. Complete What-If E2E Result
Status: FIXED + RUNTIME VERIFIED

- Management login executed successfully.
- Scenario creation executed successfully.
- `ROOM_UNAVAILABLE` scenario created and simulated.
- Affected class data inspected at runtime.
- Metrics inspected.
- Explanations inspected.
- Review flow executed.
- Approval/publish flow executed.
- Published version verified.
- Overrides verified.
- Affected student/faculty notifications verified.
- Updated timetable/session state verified.
- Revert behavior checked where supported.
- Captured evidence included scenario ID, run ID, version ID, affected class count, reassigned count, unresolved count, room changes, notifications, publish status, and revert status.

## 10. Regression Test Results
Status: FIXED + RUNTIME VERIFIED

Executed suites:
- `pytest test_management.py` → passed
- `pytest test_student_portal.py` → passed
- `pytest test_faculty_portal.py` → passed
- `pytest test_identity.py` → passed
- `pytest test_academics.py` → passed
- `pytest test_events.py` → passed
- `pytest test_food.py` → passed
- `pytest test_actions.py` → passed
- `pytest test_phase1j_focused.py` → passed

Prohibited suite not run:
- `test_api.py` → intentionally not executed

## 11. Frontend Build/Lint
Status: FIXED + RUNTIME VERIFIED

- `npm run build` → passed
- `npm run lint` → passed
- No blocking frontend failures introduced by the Phase 1J validation scope.

## 12. Database Safety
Status: FIXED + RUNTIME VERIFIED

- `campus.db` accessed? NO
- Port `8000` contacted? NO
- `test_api.py` run? NO
- Isolated database used? YES — `backend/phase1j-e2e.sqlite`
- Isolated backend port: `8766`
- Isolated frontend port: `5182`
- Temporary validation files cleaned? YES

## 13. Remaining Issues
Status: NOT IMPLEMENTED

- No blocking runtime, regression, or build/lint issues remained after the isolated validation pass.
- No production database or prohibited runtime paths were touched.

## 14. Competition Readiness
READY
