"""Comprehensive M2-M4 API test suite."""
import httpx
import json
import sys

BASE = "http://localhost:8000"
c = httpx.Client(base_url=BASE, timeout=30.0)
passed = 0
failed = 0
total = 0


def test(name, condition, detail=""):
    global passed, failed, total
    total += 1
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name} -- {detail}")


def login(email="management@demo.local", password="Demo@1234"):
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    return r.json()["access_token"]


# --- Authentication ---
print("\n=== M1: Authentication ===")
token_mgmt = login("management@demo.local")
test("Management login", token_mgmt is not None)

r = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token_mgmt}"})
test("Auth /me returns user", r.status_code == 200 and r.json()["role"] == "MANAGEMENT")

token_student = login("student.3cse-a@demo.local")
test("Student login", token_student is not None)

token_faculty = login("faculty.cse1@demo.local")
test("Faculty login", token_faculty is not None)

mgmt_headers = {"Authorization": f"Bearer {token_mgmt}"}
student_headers = {"Authorization": f"Bearer {token_student}"}
faculty_headers = {"Authorization": f"Bearer {token_faculty}"}

# --- M1: Campus Data ---
print("\n=== M1: Campus Data ===")
r = c.get("/api/blocks")
test("GET /blocks returns data", r.status_code == 200 and len(r.json()) >= 1)

r = c.get("/api/blocks/block_A/floors")
test("GET /floors returns 7", r.status_code == 200 and len(r.json()) == 7, f"got {len(r.json()) if r.status_code == 200 else r.text}")

r = c.get("/api/blocks/block_A/rooms")
test("GET /rooms returns 62", r.status_code == 200 and len(r.json()) == 62, f"got {len(r.json()) if r.status_code == 200 else r.text}")

# --- M2: Timetable & State ---
print("\n=== M2: Timetable & State ===")
r = c.get("/api/state/overview", headers=mgmt_headers)
if r.status_code == 200:
    data = r.json()
    test("State overview returns counts", data["total_entries"] == 559, f"got {data['total_entries']}")
    test("State overview has sections", data["total_sections"] == 27, f"got {data['total_sections']}")
    test("State overview has faculty", data["total_faculty"] >= 50, f"got {data['total_faculty']}")
else:
    test("State overview endpoint", False, r.text)

r = c.get("/api/timetable/me", headers=student_headers)
test("Student timetable returns entries", r.status_code == 200 and len(r.json()) > 0, f"status={r.status_code}, count={len(r.json()) if r.status_code == 200 else r.text}")

r = c.get("/api/timetable/me", headers=faculty_headers)
test("Faculty timetable returns entries", r.status_code == 200 and len(r.json()) > 0, f"status={r.status_code}, count={len(r.json()) if r.status_code == 200 else r.text}")

r = c.get("/api/timetable/section/sec_3cse_a", headers=mgmt_headers)
test("Section timetable returns entries", r.status_code == 200 and len(r.json()) > 0, f"status={r.status_code}")

# --- M3: Scenario Simulation ---
print("\n=== M3: Scenario Simulation ===")

# Create scenario
r = c.post("/api/scenarios", json={
    "name": "Test: A101-A104 Unavailable P2",
    "category": "ROOM_UNAVAILABLE",
    "changes": [{
        "type": "ROOM_UNAVAILABLE",
        "payload": {
            "room_ids": ["room_A101", "room_A102", "room_A103", "room_A104"],
            "time_from": "10:25",
            "time_to": "11:20"
        }
    }]
}, headers=mgmt_headers)
test("Create scenario", r.status_code == 200, r.text if r.status_code != 200 else "")
scenario_id = r.json()["id"] if r.status_code == 200 else None
test("Scenario status is DRAFT", r.json().get("status") == "DRAFT" if scenario_id else False)

# List scenarios
r = c.get("/api/scenarios", headers=mgmt_headers)
test("List scenarios", r.status_code == 200 and len(r.json()) >= 1)

# Simulate
if scenario_id:
    r = c.post(f"/api/scenarios/{scenario_id}/simulate", json={
        "strategies": ["MIN_DISRUPTION", "MIN_WALKING", "MIN_WASTE"],
        "time_limit_sec": 8
    }, headers=mgmt_headers)
    test("Simulate scenario", r.status_code == 200, r.text[:200] if r.status_code != 200 else "")
    if r.status_code == 200:
        sim = r.json()
        test("Simulation has affected entries", sim["affected_count"] > 0, f"affected={sim['affected_count']}")
        test("Simulation has options", len(sim["options"]) >= 1, f"options={len(sim['options'])}")
        test("Simulation has change descriptions", len(sim["change_descriptions"]) >= 1)

        opt1 = sim["options"][0]
        test("Option 1 status is FEASIBLE or PARTIAL", opt1["status"] in ("FEASIBLE", "PARTIAL"), opt1["status"])
        test("Option 1 has assignments", len(opt1["assignments"]) > 0, f"assignments={len(opt1['assignments'])}")
        test("Option 1 has metrics", "room_changes" in opt1["metrics"])
        test("Option 1 has explanations", len(opt1["explanations"]) > 0)
        test("Solver time is reasonable (<5000ms)", opt1["solve_ms"] < 5000, f"solve_ms={opt1['solve_ms']}")

        # Verify distinct options
        if len(sim["options"]) > 1:
            sigs = set()
            for opt in sim["options"]:
                sig = str(sorted(opt["assignments"].items()))
                sigs.add(sig)
            test("Options are distinct", len(sigs) == len(sim["options"]), f"unique={len(sigs)} of {len(sim['options'])}")

    # Get stored results
    r = c.get(f"/api/scenarios/{scenario_id}/result", headers=mgmt_headers)
    test("Get stored simulation result", r.status_code == 200)

# --- M3: Scenario from preset ---
print("\n=== M3: Scenario Presets ===")
r = c.post("/api/scenarios/presets/hero_event", headers=mgmt_headers)
test("Create from preset", r.status_code == 200, r.text[:200] if r.status_code != 200 else "")
preset_id = r.json()["id"] if r.status_code == 200 else None

if preset_id:
    r = c.post(f"/api/scenarios/{preset_id}/simulate", json={}, headers=mgmt_headers)
    test("Simulate preset scenario", r.status_code == 200, r.text[:200] if r.status_code != 200 else "")

# --- M3: Stress test scenario ---
print("\n=== M3: Stress Test ===")
r = c.post("/api/scenarios/presets/stress_test_5", headers=mgmt_headers)
stress_id = r.json()["id"] if r.status_code == 200 else None
if stress_id:
    r = c.post(f"/api/scenarios/{stress_id}/simulate", json={}, headers=mgmt_headers)
    test("Stress test simulation", r.status_code == 200, r.text[:200] if r.status_code != 200 else "")
    if r.status_code == 200:
        sim = r.json()
        test("Stress test has many affected", sim["affected_count"] > 10, f"affected={sim['affected_count']}")

# --- M3: Strength change ---
print("\n=== M3: Strength Change ===")
r = c.post("/api/scenarios", json={
    "name": "Test: 3CSE-A Strength 63->75",
    "changes": [{"type": "CHANGE_STRENGTH", "payload": {"section_id": "sec_3cse_a", "new_strength": 75}}]
}, headers=mgmt_headers)
strength_id = r.json()["id"] if r.status_code == 200 else None
if strength_id:
    r = c.post(f"/api/scenarios/{strength_id}/simulate", json={}, headers=mgmt_headers)
    test("Strength change simulation", r.status_code == 200)

# --- M3: RBAC ---
print("\n=== M3: RBAC ===")
r = c.post("/api/scenarios", json={"name": "Student try", "changes": [{"type": "STRESS_TEST", "payload": {"k": 1}}]}, headers=student_headers)
test("Student cannot create scenario", r.status_code == 403, f"got {r.status_code}")

# --- M4: Approval & Publish ---
print("\n=== M4: Approval & Publish ===")

if scenario_id:
    # Review scenario
    r = c.post(f"/api/scenarios/{scenario_id}/review", headers=mgmt_headers)
    test("Review scenario", r.status_code == 200, r.text[:200] if r.status_code != 200 else "")

    # Get run_id from stored results
    r = c.get(f"/api/scenarios/{scenario_id}/result", headers=mgmt_headers)
    run_id = None
    if r.status_code == 200 and r.json().get("options"):
        run_id = r.json()["options"][0]["run_id"]

    if run_id:
        # Approve and Publish
        pub_r = c.post(
            f"/api/scenarios/{scenario_id}/approve-publish",
            json={"run_id": run_id, "comment": "Demo publish"},
            headers=mgmt_headers
        )
        test("Approve and Publish", pub_r.status_code == 200, pub_r.text if pub_r.status_code != 200 else "")
        if pub_r.status_code == 200:
            version_id = pub_r.json()["version_id"]

            # Verify Version exists
            v_r = c.get("/api/versions", headers=mgmt_headers)
            test("Published version exists in list", any(v["id"] == version_id for v in v_r.json()), v_r.text)

            # Verify Revert
            rev_r = c.post(f"/api/versions/{version_id}/revert", headers=mgmt_headers)
            test("Revert version", rev_r.status_code == 200, rev_r.text)

# --- Notifications ---
print("\n=== M4: Notifications ===")
r = c.get("/api/notifications", headers=student_headers)
test("Student can list notifications", r.status_code == 200)

r = c.get("/api/notifications", headers=faculty_headers)
test("Faculty can list notifications", r.status_code == 200)

# --- Versions ---
print("\n=== M4: Versions ===")
r = c.get("/api/versions", headers=mgmt_headers)
test("List versions", r.status_code == 200)

# --- Summary ---
print(f"\n{'='*60}")
print(f"RESULTS: {passed}/{total} passed, {failed} failed")
print(f"{'='*60}")
sys.exit(0 if failed == 0 else 1)
