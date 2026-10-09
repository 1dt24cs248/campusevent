# Final A-Block Data Population Report

## Status

The isolated competition database now contains the owner-supplied A-Block structure and student data, configured curricula and teaching relationships, and safely assignable timetable entries. It is **not a complete room-feasible timetable**: where no known-capacity, suitable room was available, synthetic schedule requests remain explicitly `UNRESOLVED`; no room or capacity was guessed.

## Database and Safety

- Target: `backend/data/campus_demo.db`, using `DATABASE_URL=sqlite:///./data/campus_demo.db` from `backend/`.
- Protected database: `backend/campus.db` was not opened with SQLite, migrated, seeded, reset, or written.
  - Before: 2,027,520 bytes; last modified `2026-10-08T13:58:16.9413208+05:30`.
  - After: 2,027,520 bytes; last modified `2026-10-08T13:58:16.9413208+05:30`.
- Demo DB before this continuation: 581,632 bytes; last modified `2026-10-08T15:15:54.0313511+05:30`.
- Demo DB after population and the PDF-roster spelling correction: 827,392 bytes; last modified `2026-10-08T15:44:57.8517017+05:30`.
- No application startup or migration was run. `test_api.py` was not run. Port 8000 was not used.

## Populated Data and Provenance

- A-Block: 1 block, 7 floors, 61 rooms/locations, 8 departments.
- Sections: 31 total. The original 29 owner-supplied sections remain, and synthetic CSE 1A and CSE 1B were added with explicitly `SYNTHETIC` strength 60 each.
- Students: 64 in CSE 3A. All seven owner-provided names remain `REAL`; 57 count-only placeholders remain `SYNTHETIC`.
- Faculty: 15 total:
  - 10 names sourced from the 5A/5B PDF faculty tables.
  - Swetha and Parvathish: `REAL` identities supplied by the owner.
  - Faculty CSE-01, Faculty ISE-01, and Faculty Engineering-01: `SYNTHETIC`.
- Subjects: 127 total:
  - 4 owner-provided `REAL` subjects: EDC, DBMS, Python, DAA.
  - ML is both owner-provided and present in the PDF (`REAL` + `REAL_TIMETABLE_PDF`).
  - 7 additional PDF subjects: FCG, TOC, Next Generation Embedded Lab, PE-CNS, MAD, RM, and EVS.
  - 115 generated subjects are `SYNTHETIC`; their descriptions state they are demonstration curricula, not a verified DSATM syllabus.
- Timetable entries: 44 total:
  - 34 `REAL_TIMETABLE_PDF` rows (17 for 5A→CSE 3A and 17 for 5B→CSE 3B).
  - 10 `SYNTHETIC` first-year theory entries (5 each for CSE 1A and CSE 1B).
- Every one of the 31 sections has 5–8 curriculum subjects when its explicit configured teaching relationships and imported PDF rows are counted.
- Generated curriculum/section relationships are stored in `competition_teaching_relationships` in `settings`; each record names the faculty, subject, section, year, and `SYNTHETIC_CONFIGURED` provenance. There are 186 such records. These are not owner-provided section assignments.

## Faculty → Subject → Section → Year

### Owner-provided identities; configured section assignments

The identities and subjects are `REAL`. The section-level mappings below are `SYNTHETIC_CONFIGURED` as instructed.

- Swetha:
  - Python → CSE 1A, CSE 1B → Year 1.
  - EDC → CSE 2A, CSE 2B → Year 2.
  - DBMS → CSE 2A, CSE 2B → Year 2.
- Parvathish:
  - DAA → CSE 2A, CSE 2B → Year 2.
  - ML → CSE 3A, CSE 3B → Year 3.

### PDF-derived theory assignments

Each relationship below is evidenced by a PDF grid entry; the faculty names are taken from the corresponding PDF subject/faculty table. The timetable rows are `REAL_TIMETABLE_PDF`.

| Faculty | Subject | Section | Year |
|---|---|---|---:|
| Sanjay Das | FCG (BCS501) | CSE 3A | 3 |
| Swathi A | TOC (BCS503) | CSE 3A | 3 |
| Keerthana Shankar | PE-CNS (BCS515B) | CSE 3A | 3 |
| Sushanth Kumar | ML (BCS502) | CSE 3A | 3 |
| Shalini S | RM (BRM507A) | CSE 3A | 3 |
| Meghana Nigam | FCG (BCS501) | CSE 3B | 3 |
| Shivanna K | TOC (BCS503) | CSE 3B | 3 |
| Asha Latha | PE-CNS (BCS515B) | CSE 3B | 3 |
| Usha K C | ML (BCS502) | CSE 3B | 3 |
| Dasari Bhulakshmi | RM (BRM507A) | CSE 3B | 3 |

The 5B subject/faculty table spells the RM instructor “Dasari Bhulakshmi”; its class-teacher line spells the name “Dasari Bhuvalakshmi.” The stored teaching identity follows the subject/faculty table and retains the PDF initials DB.

### Generated faculty assignments

All assignments in this subsection are `SYNTHETIC_CONFIGURED`. Each subject is stored as a separate faculty→subject→section→year relationship; the grouped listing below combines sections only where the curriculum is shared.

- **Faculty CSE-01**
  - Year 1, CSE 1A/1B: CSE1-MATH, CSE1-PHY, CSE1-CHEM, CSE1-ENG, CSE1-ELEC, CSE1-GRAPH, CSE1-PROG-LAB.
  - Year 2, CSE 2A/2B: CSE2-DSA, CSE2-MATH, CSE2-OOP, CSE2-CO, CSE2-LAB. DAA, DBMS, and EDC are assigned to the named faculty above.
  - Year 4, CSE 4A/4B: CSE4-AI, CSE4-CLOUD, CSE4-SEC, CSE4-ELECT, CSE4-PROJ, CSE4-PROF, CSE4-PROJ-LAB.
  - Data Science: each of DS 2A/2B, DS 3A/3B, and DS 4A/4B receives its year-specific six-subject set (`MATH`, `DATA`, `AI`, `SYS`, `ELECT`, `LAB`).
  - AI/ML: AIML 2A, AIML 3A, and AIML 4A each receive their year-specific six-subject set (`MATH`, `DATA`, `AI`, `SYS`, `ELECT`, `LAB`).
  - Cybersecurity: CYBER 2 and CYBER 3 each receive their year-specific six-subject set (`MATH`, `DATA`, `AI`, `SYS`, `ELECT`, `LAB`).
- **Faculty ISE-01**
  - Year 2, ISE 2A/2B/2C; Year 3, ISE 3A/3B; Year 4, ISE 4A/4B/4C.
  - Each section receives its six year-specific subjects, comprising five theory subjects and one lab.
- **Faculty Engineering-01**
  - CIVIL 2 and MECH 2 → Year 2; CIVIL 3 and MECH 3 → Year 3.
  - Each section receives its six year-specific subjects, comprising five theory subjects and one lab.

These generated assignments are explicit rather than inferred from a faculty-to-department default at timetable runtime. Synthetic teaching plans without safe room/time assignments are not represented as booked timetable entries.

## Timetable and Unresolved PDF Mappings

### Imported PDF rows

The supplied fifth-semester timetable is used as third-year CSE source material:

- 5A → CSE 3A; 17 reliably mapped theory rows were imported.
- 5B → CSE 3B; 17 reliably mapped theory rows were imported.
- All 34 rows have `REAL_TIMETABLE_PDF` provenance and preserve source section, weekday, period, subject, and faculty in the timetable records.
- No PDF classroom was assigned. All 34 source room mappings are `NEEDS_REVIEW`:
  - 5A lists room 202; the candidate A202 in the room master is an ISE classroom.
  - 5B lists room 203; the candidate A203 in the room master is an ISE classroom.
  - No replacement room was guessed.

### Exact source rows retained as `NEEDS_REVIEW`

The following 10 unresolved 5A/5B grid items are recorded in `competition_timetable_review.unmapped_pdf_rows`:

| Source section | Day(s) | Source row | Reason |
|---|---|---|---|
| 5A | Wednesday | CG Lab / Next Gen Lab; B1/B2 instructor splits | Lab groups, period span, and room cannot be safely resolved. |
| 5A | Friday | CG Lab / Next Gen Lab; B1/B2 instructor splits | Lab groups, period span, and room cannot be safely resolved. |
| 5A | Monday | ML Lab; initials SK, RKP, RS | Lab room and multi-faculty/group allocation are ambiguous. |
| 5A | Wednesday/Thursday | NPTEL / MOOC blocks | Merged cells do not identify a single period/subject/faculty assignment. |
| 5A | Friday | EVS | Faculty initials are not unambiguous. |
| 5B | Monday | CG Lab / Next Gen Lab; B1/B2 instructor splits | Lab groups, period span, and room cannot be safely resolved. |
| 5B | Tuesday | CG Lab / Next Gen Lab; B1/B2 instructor splits | Lab groups, period span, and room cannot be safely resolved. |
| 5B | Wednesday | ML Lab; multiple faculty initials | Lab room and group/period allocation are ambiguous. |
| 5B | Thursday | EVS | No reliable faculty initial is associated with the cell. |
| 5A/5B | Saturday | PBL-MAD, placement activity, NSS/Yoga/workshop | Non-period Saturday activity, outside the requested Monday-Friday timetable. |

The PDF lab-room references remain unresolved, without substitute rooms:

- `210`: no A210 exists in the supplied room master.
- `206`: A206 is an ISE classroom, not a lab.
- `305`: A305 is the Cyber 2 classroom, not a lab.
- `506`: A506 is owner-confirmed empty.

5C, 5D, 5E, and 5F each have one `NEEDS_REVIEW` record with their extracted source-page text retained. They have no target-section mapping and were not created as sections. The only section mappings used are 5A→CSE 3A and 5B→CSE 3B.

### Synthetic schedule status

- CSE 1A and CSE 1B each have five Monday-Friday theory entries using known-capacity SH01 (90) and SH02 (75), respectively. Both synthetic section strengths are 60.
- All remaining synthetic weekly period/lab requests are explicit `UNRESOLVED`: 166 period requests. No suitable known-capacity classroom/lab was safely available under the hard capacity rule; all other 59 room capacities remain NULL.
- 10 additional curriculum-only relationships have no separate weekly period requested, to keep the sections near five theory periods.
- No unresolved request has been represented as a scheduled or feasible timetable entry.
- Therefore, only the 10 first-year synthetic entries are actual `SYNTHETIC` timetable entries; the other synthetic plans remain unresolved rather than being fabricated.

## Validation Results

| Check | Result |
|---|---|
| CSE 3A / CSE 3B | Present; strengths remain 64 / 58. |
| Seven named students | All seven remain in CSE 3A. |
| Swetha / Parvathish | Present; all ten configured mappings above are recorded with subject, section, and year. |
| Faculty total | 15 (10 PDF-source, 2 owner-named, 3 synthetic). |
| Curriculum coverage | 31 sections; each has 5–8 subjects. |
| Timetable provenance/count | 34 `REAL_TIMETABLE_PDF`; 10 `SYNTHETIC`. |
| Section double-booking | 0 duplicate section/day/period assignments among the 44 scheduled entries. |
| Faculty double-booking | 0 duplicate faculty/day/period assignments among the 44 scheduled entries. |
| Room double-booking | 0 duplicate assigned room/day/period assignments among the 44 scheduled entries. |
| Capacity | 0 assigned entries use unknown capacity or exceed known room capacity. |
| PDF room assignment | 0 of 34 PDF entries assigned a conflicting/guessed room. |
| 5C–5F | Four source pages recorded as `NEEDS_REVIEW`; no corresponding sections created. |
| Unknown capacities | 59 remain NULL; the only known capacities are SH01=90 and SH02=75, both `REAL`. |
| Navigator | 61 existing room-linked nodes remain; no coordinates or navigation edges were invented. |
| Food | Food locations, menus, and menu items remain empty. |
| Attendance/marks | Attendance sessions/records, assessments, and academic marks remain empty. |
| Referential integrity | `PRAGMA foreign_key_check` returned no violations. |
| Protected DB | `campus.db` size and last-modified timestamp match the pre-population metadata above. |

## Important Limitation

This is a provenance-conscious populated demo, not a fully scheduled campus timetable. Unknown room capacities and conflicting PDF room identifiers remain explicit blockers. Only the 44 validated entries above are booked; unresolved schedule requests and source mappings must not be presented as confirmed classes or room allocations.
