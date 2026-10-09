# Decisions Log

## Architecture Decisions

1. **SQLite as default DB** - Using SQLite for zero-install setup per spec. Schema avoids SQLite-only features for PostgreSQL compatibility.
2. **Polling over WebSockets** - Using TanStack Query refetchInterval (4-5s) per spec; no SSE/WebSocket.
3. **No Docker/Redis/Celery** - Single backend process, single frontend dev server per spec.
4. **Timetable PDF** - Found `FFINAL-5th SEM CSE TT.pdf` in data/. Will attempt extraction with pdfplumber, import only reliable mappings, queue unclear ones for Admin review.
5. **Tailwind CSS version** - Using Tailwind CSS v4 with @tailwindcss/vite plugin for clean Vite integration per spec requirement.
6. **Demo clock default** - Setting DEMO_NOW to empty (uses real time) by default; management can set via Admin.
7. **Navigation graph costs** - Using relative walking-effort units (same_floor_cost=1, vertical_cost=3 per floor) as no real distance data provided.
8. **Lab batches** - Default lab_batches=2 per spec (ESTIMATED, editable).
9. **Background sections** - Creating synthetic background sections for ISE, ME, CV, DS, AI departments exactly as specified in PART 4 to ensure realistic room occupancy.
10. **Synthetic timetable density** - Starting with DENSITY=0.65 per spec, will adjust if initial allocation is infeasible.
11. **First-year sections** - Creating 1-A (66), 1-B (68), 1-C (70) with home rooms B05, SH-01, SH-02 as ESTIMATED per spec.
12. **Home room as soft preference** - Home room mapping stored as Section.home_room_id, used as soft preference weight in CP-SAT, never a hard constraint.
13. **Capacity strict by default** - capacity_basis=STRICT_ENROLLMENT, attendance_factor=1.0 per spec default.
14. **Faculty naming** - Using "Faculty CSE-01" format for synthetic faculty per spec.
15. **OR-Tools solver seed** - Fixed random_seed=42 for deterministic output.
