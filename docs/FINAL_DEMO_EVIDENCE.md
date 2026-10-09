# Final Demo Evidence

Runtime verification used the existing frontend on port 5182 and backend on port 8766 with `DATABASE_URL=sqlite:///./phase1j-e2e.sqlite`. The backend was restarted once after the targeted changes so the live process loaded them; it was not reseeded. `campus.db` and port 8000 were not used. The browser tests below ran against the validation records in the isolated database; no production data was created.

| Workflow | Status | Evidence |
|---|---|---|
| Backend startup | RUNTIME VERIFIED | After the single required reload, `GET /health` returned `{"status":"ok"}` on port 8766. Frontend port 5182 loaded the Management and Student pages and showed “Backend connected” / “Live”. |
| Authentication | RUNTIME VERIFIED | Management, Faculty, and Student validation credentials authenticated successfully. The browser authenticated as Management and Student and opened role-specific pages. |
| What-If ROOM_UNAVAILABLE | RUNTIME VERIFIED | Browser-created scenario `scen_d175f621ef`, run `run_b44e23c4a1`. V101 closure: 1 affected, 1 reassigned, 0 unchanged, 0 unresolved. The result UI showed CSE101 — Algorithms, 3CSE-A, Year 3, Validation Faculty, Tuesday 11:35–13:25, V101 → V201, strength 60, capacity 80, required PROJECTOR, `REASSIGNED`, and the optimizer explanation. |
| What-If FLOOR_UNAVAILABLE | PARTIALLY VERIFIED | Browser-created scenario `scen_ca106ef03a`, run `run_565f17f703`. The room selector was absent; the floor selector showed only actual database floors (“1st Floor”, “2nd Floor”). Selecting the actual 1st Floor previewed only V101 and V102 as unavailable; simulation affected 1 class, reassigned 1 to V201, and left 0 unresolved. This isolated database contains no Basement, Ground Floor, or 3rd–5th floor records, so those options cannot be offered without inventing floors. |
| What-If STRESS_TEST | RUNTIME VERIFIED | Browser-created scenario `scen_97cb4560a2`, run `run_6ef10ef183`. Condition shown: requested closure of 5 busiest rooms; 2 occupied rooms selected (V101, V201). Two classes affected; 1 reassigned to V102 and 1 unresolved. Conflicts: 0 before / 0 after. Enrollment-to-allocated-seat utilization ratio: 0.8 before / 0.8571 after (explicitly labelled as a ratio, not a percentage). Capacity-pressure classes: 0 before / 1 after. Walking effort 3; wasted capacity 10. The UI displayed both decision rows and reasons. |
| Faculty My Sections | PARTIALLY VERIFIED | Authenticated faculty API returned the actual timetable-derived relationship Validation Faculty → CSE101 Algorithms → 3CSE-A → Year 3. Two timetable entries source that same relationship. No DBMS relationship appeared. This validation dataset has only one distinct relationship; the My Sections page itself was not reopened in this pass. |
| Academic Management | PARTIALLY VERIFIED | Previous browser observation showed Students 1, Faculty 1, Departments 1 (CSE), Sections 1, Subjects 1, Rooms 3, Today’s classes 0, Pending requests 0, Event proposals 0, Assessments 0, Attendance 0, Announcements 0. FIRST_YEAR was not presented as a department. Validation records appeared without a separate synthetic-data label. |
| Student AI | PARTIALLY VERIFIED | Authenticated Student API returned “Your next scheduled class is CSE101 — Algorithms at 11:35 in room V101” and “Your subjects are: CSE101 — Algorithms,” matching the student’s timetable and section. Browser chat was not repeated in this pass. |
| Faculty AI | PARTIALLY VERIFIED | Authenticated Faculty API returned “Your assigned subjects are: CSE101 — Algorithms” and “Your assigned sections are: 3CSE-A,” matching the faculty timetable. Browser chat was not repeated in this pass. |
| Management AI | RUNTIME VERIFIED | Browser asked “How many campus rooms are registered?” and displayed “There are 3 campus rooms registered.” Live API also answered sections (1), active faculty (1), active students (1), active/allocatable rooms (V101, V102, V201), and 1st-floor rooms (V101, V102). The same management-only query as Student received the existing classroom-only fallback, not the management count. |
| Student SOS | PARTIALLY VERIFIED | Browser saved contact `contact_e03661c6f73149` for the isolated validation student, refreshed, and saw it persist as Runtime Validation Contact · Parent · `********100`. Call/SMS links were present (`tel:` and `sms:`). Clicking Send SMS produced the honest status that the device must confirm and no message was sent; this browser reported `net::ERR_ABORTED` for the `sms:` URI, so external device handling was not verified. Focused ownership tests confirmed another student cannot list, edit, or delete the contact. |
| Campus Navigator | PARTIALLY VERIFIED | Browser search resolved actual room V101 and displayed Validation Block · 1st Floor · capacity 70, plus an honest location description stating no mapped turn-by-turn route is available; no GPS was claimed. A101 was not in the isolated dataset and the UI said no campus room matches. A102/A105 likewise have no records in this dataset. |
| Campus Food | NO DATA TO VERIFY | Management showed no stalls and no menus; student-visible published food data was empty. No food data was created. |

## Validation

- Backend regression suite: **70 passed, 0 failed** (`test_management.py`, `test_student_portal.py`, `test_faculty_portal.py`, `test_identity.py`, `test_academics.py`, `test_events.py`, `test_food.py`, `test_actions.py`, `test_phase1j_focused.py`).
- Focused changed-workflow tests: **24 passed**.
- `test_api.py`: **not run**.
- Frontend build: **passed** (`npm run build`); Vite emitted the existing large-chunk advisory.
- Frontend lint: **passed** (`npm run lint`); one warning in `src/context/AuthContext.tsx` about fast-refresh exports.

## CRITICAL FIXES REQUIRED
1. The Phase 1J database only has first- and second-floor records; Basement, Ground Floor, and floors 3–5 remain unverified and are intentionally not fabricated.
2. The Phase 1J campus map contains only validation rooms and no turn-by-turn graph route; actual A101/A102/A105 lookup cannot be demonstrated from this dataset.
3. Device-level SMS/call handoff is environment-dependent. The app offers `tel:` and `sms:` links and clearly avoids claiming delivery, but the integrated browser could not launch the SMS URI.

## OPTIONAL FIXES
1. Reopen Faculty My Sections and Student/Faculty AI in the browser for same-pass UI evidence; current evidence for those flows is authenticated live API output.
2. Add real campus floor/location records and a mapped route graph through the proper data process before claiming coverage beyond this isolated validation dataset.

No competition-readiness claim is made. The core What-If room and stress workflows execute, and floor closure now works for actual recorded floors; remaining limits are listed above.
